"""Pinned Common Crawl download preflight. Extraction is a subsequent gated step.

python eval/sybil_import.py --directory <offline storage> [--download]
No graph bytes are downloaded unless --download is explicit and preflight passes.
"""

import argparse
import hashlib
import json
import math
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

RELEASE = "cc-main-2026-aug-sep-oct"
MANIFEST_URL = "https://index.commoncrawl.org/graphinfo.json"
BASE = f"https://data.commoncrawl.org/projects/hyperlinkgraph/{RELEASE}/domain/"
FILES = tuple(
    f"{RELEASE}-domain{suffix}"
    for suffix in (
        ".graph",
        ".properties",
        "-t.graph",
        "-t.properties",
        "-vertices.txt.gz",
    )
)
GIB = 1024**3
MIB = 1024**2


def storage_check(
    sizes: dict[str, int], directory: Path, budget: int, reserve: int
) -> dict:
    """Source sizes are exact; derived-file reserve is a declared planning allowance."""
    if budget <= 0 or reserve < 0 or any(size <= 0 for size in sizes.values()):
        raise ValueError(
            "Positive source sizes/budget and nonnegative reserve required"
        )
    existing = sum(
        min((directory / name).stat().st_size, size)
        for name, size in sizes.items()
        if (directory / name).is_file()
    )
    source = sum(sizes.values())
    required = source + reserve
    additional = source - existing + reserve
    free = shutil.disk_usage(directory).free
    return {
        "source_bytes": source,
        "derived_reserve_bytes": reserve,
        "required_bytes": required,
        "additional_bytes": additional,
        "budget_bytes": budget,
        "free_bytes": free,
        "can_download": required <= budget and additional <= free,
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_s3_etag(path: Path, etag: str, size: int) -> None:
    """Verify single-part or standard-size multipart S3 object identity."""
    value = etag.strip('"')
    _, separator, count_text = value.partition("-")
    if not separator:
        part_sizes = (size,)
    else:
        count = int(count_text)
        candidates = (5 * MIB, *(2**power * MIB for power in range(3, 14)))
        part_sizes = tuple(
            part for part in candidates if math.ceil(size / part) == count
        )
        if len(part_sizes) != 1:
            raise ValueError(f"Cannot infer S3 multipart size for ETag {etag}")
    part_size = part_sizes[0]
    parts = []
    with path.open("rb") as stream:
        while chunk := stream.read(part_size):
            parts.append(hashlib.md5(chunk).digest())
    actual = (
        parts[0].hex()
        if not separator
        else f"{hashlib.md5(b''.join(parts)).hexdigest()}-{len(parts)}"
    )
    if actual != value:
        raise ValueError(f"{path.name}: remote S3 object identity mismatch")


def open_with_retry(request: Request, timeout: int):
    for attempt in range(50):
        try:
            return urlopen(request, timeout=timeout)
        except (TimeoutError, URLError, ConnectionError) as error:
            if attempt == 49:
                raise
            delay = min(30, 2 * (attempt + 1))
            print(
                f"Metadata request interrupted ({error}); retrying in {delay}s",
                flush=True,
            )
            time.sleep(delay)
    raise RuntimeError("Metadata retry limit exhausted")


def download(
    url: str,
    path: Path,
    size: int,
    block_size: int = 16 * 1024 * 1024,
    etag: str | None = None,
) -> str:
    """Resume only when the server confirms the exact requested byte range."""
    offset = path.stat().st_size if path.exists() else 0
    if offset > size:
        raise ValueError(f"{path.name}: existing file exceeds published size")
    if block_size < 1:
        raise ValueError("Download block size must be positive")
    while offset < size:
        end = min(offset + block_size, size) - 1
        request = Request(url, headers={"Range": f"bytes={offset}-{end}"})
        with urlopen(request, timeout=60) as response:
            content_range = response.headers.get("Content-Range", "")
            parts = content_range.removeprefix("bytes ").replace("/", "-").split("-")
            if (
                response.status != 206
                or len(parts) != 3
                or int(parts[0]) != offset
                or int(parts[1]) > end
                or int(parts[2]) != size
            ):
                raise ValueError(f"{path.name}: server did not confirm resume range")
            response_end = int(parts[1]) + 1
            with path.open("ab" if offset else "wb") as target:
                received = offset
                while chunk := response.read(1024 * 1024):
                    received += len(chunk)
                    if received > response_end:
                        raise ValueError(f"{path.name}: response exceeds declared size")
                    target.write(chunk)
        offset = path.stat().st_size
        if offset != received or offset <= int(parts[0]):
            raise ValueError(f"{path.name}: incomplete transfer; rerun to resume")
        print(f"{path.name}: {offset:,} / {size:,} bytes", flush=True)
    if etag:
        verify_s3_etag(path, etag, size)
    return sha256(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--budget-gib", type=float, default=60)
    parser.add_argument(
        "--derived-reserve-gib",
        type=float,
        default=20,
        help="Planning allowance, not a measured extraction requirement",
    )
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    if args.budget_gib <= 0 or args.derived_reserve_gib < 0:
        parser.error("Budget must be positive and reserve nonnegative")
    directory = args.directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    with open_with_retry(MANIFEST_URL, timeout=30) as response:
        release = next(item for item in json.load(response) if item["id"] == RELEASE)
    sizes = {}
    remote_objects = {}
    for name in FILES:
        request = Request(
            BASE + name,
            method="HEAD",
            headers={"x-amz-checksum-mode": "ENABLED"},
        )
        with open_with_retry(request, timeout=30) as response:
            sizes[name] = int(response.headers["Content-Length"])
            remote_objects[name] = {
                "etag": response.headers["ETag"],
                "checksum_crc64nvme": response.headers.get("x-amz-checksum-crc64nvme"),
            }
    report = {
        "release": release,
        "observed_at": datetime.now(UTC).isoformat(),
        "files": sizes,
        "remote_objects": remote_objects,
        "storage": storage_check(
            sizes,
            directory,
            int(args.budget_gib * GIB),
            int(args.derived_reserve_gib * GIB),
        ),
        "source": MANIFEST_URL,
        "terms": "https://commoncrawl.org/terms-of-use",
        "published_checksums": "S3 ETag verified; CRC64NVME recorded when advertised; local SHA-256 recorded",
        "stage": "download_preflight",
        "extraction_ready": False,
    }
    (directory / "preflight.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    if not report["storage"]["can_download"]:
        raise SystemExit(
            f"Storage preflight failed: required {report['storage']['required_bytes']} "
            f"bytes; additional {report['storage']['additional_bytes']} bytes"
        )
    if args.download:
        hashes = {}

        def fetch(name: str, size: int) -> tuple[str, str]:
            for attempt in range(50):
                try:
                    return name, download(
                        BASE + name,
                        directory / name,
                        size,
                        etag=remote_objects[name]["etag"],
                    )
                except (TimeoutError, URLError, ConnectionError) as error:
                    if attempt == 49:
                        raise
                    delay = min(30, 2 * (attempt + 1))
                    print(
                        f"Transfer interrupted ({error}); resuming in {delay} seconds",
                        flush=True,
                    )
                    time.sleep(delay)
            raise RuntimeError(f"{name}: retry limit exhausted")

        with ThreadPoolExecutor(max_workers=3) as workers:
            futures = [
                workers.submit(fetch, name, size) for name, size in sizes.items()
            ]
            for future in as_completed(futures):
                name, digest = future.result()
                hashes[name] = digest
                (directory / "sha256.json").write_text(
                    json.dumps(hashes, indent=2), encoding="utf-8"
                )
        print(
            "Downloads complete. WebGraph extraction and artifact validation are still required."
        )


if __name__ == "__main__":
    main()
