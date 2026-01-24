from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from litestar.types import PathType

_template_dirs: list["PathType"] = [Path("templates")]


def register_template_dirs(*paths: "PathType") -> None:
    for path in paths:
        resolved = Path(path)
        if not resolved.is_dir():
            raise ValueError(f"Template directory does not exist: {path}")
        if path not in _template_dirs:
            _template_dirs.append(path)


def get_template_dirs() -> list["PathType"]:
    return _template_dirs.copy()
