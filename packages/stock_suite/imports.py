from __future__ import annotations

import importlib
import sys
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType
from typing import Iterator


@contextmanager
def prepend_sys_path(path: Path) -> Iterator[None]:
    path_text = str(path)
    inserted = path_text not in sys.path
    if inserted:
        sys.path.insert(0, path_text)
    try:
        yield
    finally:
        if inserted:
            try:
                sys.path.remove(path_text)
            except ValueError:
                pass


def import_from_source(module_name: str, source_root: Path) -> ModuleType:
    with prepend_sys_path(source_root):
        return importlib.import_module(module_name)
