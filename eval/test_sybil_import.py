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
    with patch.object(module.shutil, "disk_usage", return_value=type("Usage", (), {"free": 50})()):
        report = module.storage_check({"graph": 10, "labels": 20}, tmp_path, 60, 25)
        assert report["required_bytes"] == 55
        assert report["additional_bytes"] == 51
        assert not report["can_download"]
        assert not module.storage_check({"graph": 10}, tmp_path, 9, 0)["can_download"]
        assert module.storage_check({"graph": 10}, tmp_path, 10, 0)["can_download"]


def test_unconfirmed_resume_preserves_file(tmp_path):
    target = tmp_path / "graph"
    target.write_bytes(b"1234")
    response = io.BytesIO(b"5678")
    response.status = 200
    response.headers = {}
    with patch.object(module, "urlopen", return_value=response):
        with pytest.raises(ValueError, match="resume range"):
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
    with patch.object(module, "urlopen", side_effect=AssertionError("No duplicate download")):
        assert module.download("https://example.test/graph", target, 8) == digest
