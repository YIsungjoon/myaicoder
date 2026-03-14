"""Tests for ModelScanner — GGUF file discovery and config matching."""

from pathlib import Path

from myaicoder.models.config import ModelProfile, ModelsConfig
from myaicoder.models.scanner import ModelScanner


def _make_config(*profiles: ModelProfile) -> ModelsConfig:
    return ModelsConfig(instances=list(profiles))


def test_scan_empty_dir(tmp_path: Path):
    """Empty directory returns no models."""
    config = _make_config()
    scanner = ModelScanner(tmp_path, config)
    assert scanner.scan() == []


def test_scan_nonexistent_dir():
    """Non-existent directory returns no models."""
    config = _make_config()
    scanner = ModelScanner("/nonexistent/path", config)
    assert scanner.scan() == []


def test_scan_finds_gguf_files(tmp_path: Path):
    """Discovers .gguf files and reports sizes."""
    (tmp_path / "model-a.gguf").write_bytes(b"x" * 1024)
    (tmp_path / "model-b.gguf").write_bytes(b"y" * (1024 * 1024 * 100))  # 100MB
    (tmp_path / "not-a-model.txt").write_text("ignore")

    config = _make_config()
    scanner = ModelScanner(tmp_path, config)
    files = scanner.scan()

    assert len(files) == 2
    names = {f.name for f in files}
    assert "model-a" in names
    assert "model-b" in names
    assert all(not f.registered for f in files)


def test_scan_matches_config_profiles(tmp_path: Path):
    """GGUF files matching config profiles get the profile name."""
    (tmp_path / "Qwen3.5-27B-Q4_K_M.gguf").write_bytes(b"x" * 1024)
    (tmp_path / "unknown.gguf").write_bytes(b"y" * 512)

    config = _make_config(
        ModelProfile(name="qwen3.5-27b", file="Qwen3.5-27B-Q4_K_M.gguf"),
    )
    scanner = ModelScanner(tmp_path, config)
    files = scanner.scan()

    registered = [f for f in files if f.registered]
    unregistered = [f for f in files if not f.registered]

    assert len(registered) == 1
    assert registered[0].name == "qwen3.5-27b"

    assert len(unregistered) == 1
    assert unregistered[0].name == "unknown"


def test_size_human_gb(tmp_path: Path):
    """Large files show GB."""
    size = int(2.5 * 1024**3)  # 2.5 GB
    (tmp_path / "big.gguf").write_bytes(b"\0" * size)

    config = _make_config()
    scanner = ModelScanner(tmp_path, config)
    files = scanner.scan()

    assert len(files) == 1
    assert files[0].size_human == "2.5GB"


def test_size_human_mb(tmp_path: Path):
    """Small files show MB."""
    (tmp_path / "tiny.gguf").write_bytes(b"\0" * (50 * 1024 * 1024))  # 50 MB

    config = _make_config()
    scanner = ModelScanner(tmp_path, config)
    files = scanner.scan()

    assert len(files) == 1
    assert files[0].size_human == "50MB"
