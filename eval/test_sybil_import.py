import importlib.util
import io
from pathlib import Path
from unittest.mock import patch

import pytest

spec = importlib.util.spec_from_file_location(
    "sybil_import", Path(__file__).with_name("sybil_import.py")
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_preflight_budget_free_space_and_resume(tmp_path):
    (tmp_path / "graph").write_bytes(b"1234")
    with patch.object(
        module.shutil, "disk_usage", return_value=type("Usage", (), {"free": 50})()
    ):
        report = module.storage_check({"graph": 10, "labels": 20}, tmp_path, 60, 25)
        assert report["required_bytes"] == 55
        assert report["additional_bytes"] == 51
        assert not report["can_download"]
        assert not module.storage_check({"graph": 10}, tmp_path, 9, 0)["can_download"]
        assert module.storage_check({"graph": 10}, tmp_path, 10, 0)["can_download"]


def test_metadata_requests_retry_network_failures():
    response = object()
    with (
        patch.object(
            module, "urlopen", side_effect=[module.URLError("offline"), response]
        ),
        patch.object(module.time, "sleep") as sleep,
    ):
        assert module.open_with_retry("https://example.test/manifest", 1) is response
    sleep.assert_called_once_with(2)


def test_unconfirmed_resume_preserves_file(tmp_path):
    target = tmp_path / "graph"
    target.write_bytes(b"1234")
    response = io.BytesIO(b"5678")
    response.status = 200
    response.headers = {}
    with (
        patch.object(module, "urlopen", return_value=response),
        pytest.raises(ValueError, match="resume range"),
    ):
        module.download("https://example.test/graph", target, 8)
    assert target.read_bytes() == b"1234"


def test_confirmed_resume_and_completed_hash(tmp_path):
    target = tmp_path / "graph"
    target.write_bytes(b"1234")
    response = io.BytesIO(b"5678")
    response.status = 206
    response.headers = {"Content-Range": "bytes 4-7/8"}
    with patch.object(module, "urlopen", return_value=response):
        digest = module.download("https://example.test/graph", target, 8)
    assert target.read_bytes() == b"12345678"
    assert digest == module.hashlib.sha256(b"12345678").hexdigest()
    with patch.object(
        module, "urlopen", side_effect=AssertionError("No duplicate download")
    ):
        assert module.download("https://example.test/graph", target, 8) == digest


def test_bounded_range_requests(tmp_path):
    first, second = io.BytesIO(b"1234"), io.BytesIO(b"5678")
    for response, start in [(first, 0), (second, 4)]:
        response.status = 206
        response.headers = {"Content-Range": f"bytes {start}-{start + 3}/8"}
    with patch.object(module, "urlopen", side_effect=[first, second]) as request:
        module.download(
            "https://example.test/graph", tmp_path / "graph", 8, block_size=4
        )
    assert [call.args[0].get_header("Range") for call in request.call_args_list] == [
        "bytes=0-3",
        "bytes=4-7",
    ]
    assert (tmp_path / "graph").read_bytes() == b"12345678"


def test_short_confirmed_range_resumes_at_actual_server_end(tmp_path):
    responses = []
    for start, body in [(0, b"1234"), (4, b"5678")]:
        response = io.BytesIO(body)
        response.status = 206
        response.headers = {"Content-Range": f"bytes {start}-{start + 3}/8"}
        responses.append(response)
    with patch.object(module, "urlopen", side_effect=responses) as request:
        module.download(
            "https://example.test/graph", tmp_path / "graph", 8, block_size=8
        )
    assert [call.args[0].get_header("Range") for call in request.call_args_list] == [
        "bytes=0-7",
        "bytes=4-7",
    ]
    assert (tmp_path / "graph").read_bytes() == b"12345678"


def test_s3_single_part_identity_rejects_self_hashed_corruption(tmp_path):
    target = tmp_path / "graph"
    target.write_bytes(b"trusted")
    etag = module.hashlib.md5(b"trusted").hexdigest()
    module.verify_s3_etag(target, etag, target.stat().st_size)
    target.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="remote S3 object identity mismatch"):
        module.verify_s3_etag(target, etag, target.stat().st_size)


def test_s3_multipart_identity(tmp_path):
    target = tmp_path / "graph"
    part = b"a" * (5 * module.MIB)
    tail = b"tail"
    target.write_bytes(part + tail)
    etag = (
        module.hashlib.md5(
            module.hashlib.md5(part).digest() + module.hashlib.md5(tail).digest()
        ).hexdigest()
        + "-2"
    )
    module.verify_s3_etag(target, etag, target.stat().st_size)
