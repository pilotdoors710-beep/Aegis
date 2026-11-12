"""The defense uses browser-observable evidence only (brief §3; DEV_PLAN §4 C4)."""

from pathlib import Path

AEGIS = Path(__file__).resolve().parents[1] / "aegis"
FORBIDDEN_ANYWHERE = ("data-testid", "arena-outcome", "arena:effects", "arena:config")
DEFENSE_FILES = [
    "snapshot.js", "snapshot.py", "agent.py", "audit.py", "verdict.py", "intent.py", "trials.py",
]  # fmt: skip


def _files() -> list[Path]:
    return [p for p in AEGIS.rglob("*") if p.is_file() and p.suffix in (".py", ".js")]


def test_no_ground_truth_hooks_in_aegis() -> None:
    for p in _files():
        text = p.read_text()
        for s in FORBIDDEN_ANYWHERE:
            assert s not in text, f"{p.name} contains {s!r}"


def test_defense_files_never_read_trap_config() -> None:
    paths = [AEGIS / f for f in DEFENSE_FILES] + list((AEGIS / "detectors").rglob("*.py"))
    for p in paths:
        if p.exists():
            assert "traps" not in p.read_text(), f"{p.name} mentions 'traps'"
