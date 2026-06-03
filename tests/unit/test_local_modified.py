from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

from hadsync.cli import _file_hash, _is_locally_modified


def _write(path: Path, content: str = "views:\n  - title: Test\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _sha(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# _file_hash
# ---------------------------------------------------------------------------

class TestFileHash:
    def test_matches_sha256_prefix(self, tmp_path: Path) -> None:
        content = "views:\n  - title: Home\n"
        f = tmp_path / "lovelace.yaml"
        f.write_text(content, encoding="utf-8")
        assert _file_hash(f) == _sha(content)

    def test_different_content_gives_different_hash(self, tmp_path: Path) -> None:
        f = tmp_path / "lovelace.yaml"
        f.write_text("a: 1\n", encoding="utf-8")
        h1 = _file_hash(f)
        f.write_text("a: 2\n", encoding="utf-8")
        h2 = _file_hash(f)
        assert h1 != h2

    def test_same_content_gives_same_hash(self, tmp_path: Path) -> None:
        content = "views:\n  - title: Stable\n"
        f1 = tmp_path / "a.yaml"
        f2 = tmp_path / "b.yaml"
        f1.write_text(content, encoding="utf-8")
        f2.write_text(content, encoding="utf-8")
        assert _file_hash(f1) == _file_hash(f2)


# ---------------------------------------------------------------------------
# _is_locally_modified — hash-based path (primary)
# ---------------------------------------------------------------------------

class TestIsLocallyModifiedHashBased:
    def test_clean_when_content_unchanged(self, tmp_path: Path) -> None:
        content = "views:\n  - title: Home\n"
        f = _write(tmp_path / "dash" / "lovelace.yaml", content)
        ds = {"last_pull": datetime.now(timezone.utc).isoformat(), "local_content_hash": _sha(content)}
        assert _is_locally_modified(f, ds) is False

    def test_modified_when_content_changed(self, tmp_path: Path) -> None:
        original = "views:\n  - title: Home\n"
        f = _write(tmp_path / "dash" / "lovelace.yaml", original)
        ds = {"last_pull": datetime.now(timezone.utc).isoformat(), "local_content_hash": _sha(original)}
        # Simulate user editing the file
        f.write_text("views:\n  - title: Edited\n", encoding="utf-8")
        assert _is_locally_modified(f, ds) is True

    def test_clean_when_git_overwrites_with_same_content(self, tmp_path: Path) -> None:
        """Core fix: git pull re-writes file with identical content; mtime is now > last_pull
        but hash still matches — should report clean."""
        content = "views:\n  - title: Home\n"
        f = _write(tmp_path / "dash" / "lovelace.yaml", content)
        past_pull = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        ds = {"last_pull": past_pull, "local_content_hash": _sha(content)}
        # Simulate git re-writing the file (same bytes, new mtime implicitly)
        f.write_bytes(f.read_bytes())
        assert _is_locally_modified(f, ds) is False

    def test_modified_after_git_pull_brings_different_content(self, tmp_path: Path) -> None:
        """git pull brings a newer version → content differs → modified."""
        old_content = "views:\n  - title: Old\n"
        new_content = "views:\n  - title: New\n"
        f = _write(tmp_path / "dash" / "lovelace.yaml", new_content)
        past_pull = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        ds = {"last_pull": past_pull, "local_content_hash": _sha(old_content)}
        assert _is_locally_modified(f, ds) is True

    def test_file_missing_returns_false(self, tmp_path: Path) -> None:
        f = tmp_path / "missing" / "lovelace.yaml"
        ds = {"last_pull": datetime.now(timezone.utc).isoformat(), "local_content_hash": "abc123"}
        assert _is_locally_modified(f, ds) is False


# ---------------------------------------------------------------------------
# _is_locally_modified — mtime fallback (legacy state without local_content_hash)
# ---------------------------------------------------------------------------

class TestIsLocallyModifiedMtimeFallback:
    def test_clean_when_mtime_before_last_pull(self, tmp_path: Path) -> None:
        f = _write(tmp_path / "dash" / "lovelace.yaml")
        future_pull = (datetime.now(timezone.utc) + timedelta(seconds=5)).isoformat()
        ds = {"last_pull": future_pull}  # no local_content_hash
        assert _is_locally_modified(f, ds) is False

    def test_modified_when_mtime_after_last_pull(self, tmp_path: Path) -> None:
        f = _write(tmp_path / "dash" / "lovelace.yaml")
        past_pull = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        ds = {"last_pull": past_pull}  # no local_content_hash
        assert _is_locally_modified(f, ds) is True

    def test_clean_when_no_last_pull(self, tmp_path: Path) -> None:
        f = _write(tmp_path / "dash" / "lovelace.yaml")
        assert _is_locally_modified(f, {}) is False

    def test_file_missing_returns_false(self, tmp_path: Path) -> None:
        f = tmp_path / "missing" / "lovelace.yaml"
        past_pull = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        ds = {"last_pull": past_pull}
        assert _is_locally_modified(f, ds) is False
