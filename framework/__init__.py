from collections.abc import Sequence
from pathlib import Path

_template_dirs: list[Path] = [Path("templates")]


def register_template_dirs(*paths: Path | str) -> None:
    """Register additional template directories for module-owned templates."""
    for path in map(Path, paths):
        if not path.is_dir():
            raise ValueError(f"Template directory does not exist: {path}")
        if path not in _template_dirs:
            _template_dirs.append(path)


def get_template_dirs() -> Sequence[Path]:
    return tuple(_template_dirs)
