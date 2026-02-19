from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class AccessLevel(str, Enum):
    GUEST = "guest"
    ENG = "eng"
    ROOT = "root"


class FSNodeType(str, Enum):
    FILE = "file"
    DIR = "dir"


@dataclass(slots=True)
class FSNode:
    path: str
    node_type: FSNodeType
    content: str = ""
    access: AccessLevel = AccessLevel.GUEST
    is_corrupted: bool = False


@dataclass(slots=True)
class OSState:
    access_level: AccessLevel = AccessLevel.GUEST
    fs: dict[str, FSNode] = field(default_factory=dict)


def normalize_path(path: str) -> str:
    if not path:
        return "/"
    path = path.strip()
    if not path.startswith("/"):
        path = "/" + path
    while "//" in path:
        path = path.replace("//", "/")
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    return path


def _has_access(node: FSNode, access_level: AccessLevel) -> bool:
    order = {
        AccessLevel.GUEST: 0,
        AccessLevel.ENG: 1,
        AccessLevel.ROOT: 2,
    }
    return order[access_level] >= order[node.access]


def list_dir(fs: dict[str, FSNode], dir_path: str, access_level: AccessLevel) -> list[str]:
    dir_path = normalize_path(dir_path)
    if dir_path != "/":
        prefix = dir_path + "/"
    else:
        prefix = "/"
    entries: set[str] = set()
    for path, node in fs.items():
        if not _has_access(node, access_level):
            continue
        if not path.startswith(prefix):
            continue
        rest = path[len(prefix):]
        if not rest:
            continue
        name = rest.split("/", 1)[0]
        entries.add(name)
    return sorted(entries)


def read_file(fs: dict[str, FSNode], file_path: str, access_level: AccessLevel) -> str:
    file_path = normalize_path(file_path)
    node = fs.get(file_path)
    if not node:
        raise KeyError(file_path)
    if not _has_access(node, access_level):
        raise PermissionError(file_path)
    if node.node_type != FSNodeType.FILE:
        raise IsADirectoryError(file_path)
    return node.content
