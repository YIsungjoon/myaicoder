"""Model file scanner — discovers GGUF files and matches against config profiles."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from myaicoder.models.config import ModelsConfig


@dataclass
class ModelFile:
    name: str
    path: Path
    size_bytes: int
    registered: bool

    @property
    def size_human(self) -> str:
        gb = self.size_bytes / (1024**3)
        if gb >= 1.0:
            return f"{gb:.1f}GB"
        mb = self.size_bytes / (1024**2)
        return f"{mb:.0f}MB"


class ModelScanner:
    """Scans a directory for GGUF model files."""

    def __init__(self, models_dir: str | Path, config: ModelsConfig):
        self._dir = Path(models_dir).expanduser()
        self._config = config

    def scan(self) -> list[ModelFile]:
        """Scan for *.gguf files and match against config profiles."""
        if not self._dir.exists():
            return []

        config_files = {p.file: p.name for p in self._config.instances}
        results: list[ModelFile] = []

        for path in sorted(self._dir.glob("*.gguf")):
            profile_name = config_files.get(path.name, path.stem)
            results.append(ModelFile(
                name=profile_name,
                path=path,
                size_bytes=path.stat().st_size,
                registered=path.name in config_files,
            ))

        return results
