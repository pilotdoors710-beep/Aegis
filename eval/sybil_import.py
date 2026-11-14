"""Pinned Common Crawl download preflight. Extraction is a subsequent gated step.

python eval/sybil_import.py --directory <offline storage> [--download]
No graph bytes are downloaded unless --download is explicit and preflight passes.
"""

import argparse
import hashlib
import json
import shutil
import time
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


def storage_check(sizes: dict[str, int], directory: Path, budget: int, reserve: int) -> dict:
    """Source sizes are exact; derived-file reserve is a declared planning allowance."""
    if budget <= 0 or reserve < 0 or any(size <= 0 for size in sizes.values()):
        raise ValueError("Positive source sizes/budget and nonnegative reserve required")
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


def download(url: str, path: Path, size: int, block_size: int = 16 * 1024 * 1024) -> str:
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
            full_response = offset == 0 and end == size - 1 and response.status == 200
            if not full_response and (
                response.status != 206
                or response.headers.get("Content-Range") != f"bytes {offset}-{end}/{size}"
            ):
                raise ValueError(f"{path.name}: server did not confirm resume range")
            with path.open("ab" if offset else "wb") as target:
                received = offset
                while chunk := response.read(1024 * 1024):
                    received += len(chunk)
                    if received > end + 1:
                        raise ValueError(f"{path.name}: response exceeds declared size")
                    target.write(chunk)
        offset = path.stat().st_size
        if offset != end + 1:
            raise ValueError(f"{path.name}: incomplete transfer; rerun to resume")
        print(f"{path.name}: {offset:,} / {size:,} bytes", flush=True)
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
    with urlopen(MANIFEST_URL, timeout=30) as response:
        release = next(item for item in json.load(response) if item["id"] == RELEASE)
    sizes = {}
    for name in FILES:
        with urlopen(Request(BASE + name, method="HEAD"), timeout=30) as response:
            sizes[name] = int(response.headers["Content-Length"])
    report = {
        "release": release,
        "observed_at": datetime.now(UTC).isoformat(),
        "files": sizes,
        "storage": storage_check(
            sizes,
            directory,
            int(args.budget_gib * GIB),
            int(args.derived_reserve_gib * GIB),
        ),
        "source": MANIFEST_URL,
        "terms": "https://commoncrawl.org/terms-of-use",
        "published_checksums": "Not advertised by the pinned release index; local SHA-256 only",
        "stage": "download_preflight",
        "extraction_ready": False,
    }
    (directory / "preflight.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if not report["storage"]["can_download"]:
        raise SystemExit(
            f"Storage preflight failed: required {report['storage']['required_bytes']} "
            f"bytes; additional {report['storage']['additional_bytes']} bytes"
        )
    if args.download:
        hashes = {}
        for name, size in sizes.items():
            for attempt in range(5):
                try:
                    hashes[name] = download(BASE + name, directory / name, size)
                    break
                except (TimeoutError, URLError, ConnectionError) as error:
                    if attempt == 4:
                        raise
                    print(f"Transfer interrupted ({error}); resuming in 2 seconds", flush=True)
                    time.sleep(2)
            (directory / "sha256.json").write_text(json.dumps(hashes, indent=2), encoding="utf-8")
        print("Downloads complete. WebGraph extraction and artifact validation are still required.")


if __name__ == "__main__":
    main()
