from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class AccessLevel(str, Enum):
    GUEST = "guest"
    ENG = "eng"
    ROOT = "root"


class Locale(str, Enum):
    EN = "en"
    ES = "es"


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
    locale: Locale = Locale.EN
    debug_enabled: bool = False
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


def _ensure_dir(fs: dict[str, FSNode], dir_path: str, access: AccessLevel) -> None:
    dir_path = normalize_path(dir_path)
    if dir_path in fs:
        return
    fs[dir_path] = FSNode(path=dir_path, node_type=FSNodeType.DIR, access=access)


def mount_files(fs: dict[str, FSNode], prefix: str, files: list[dict]) -> int:
    prefix = normalize_path(prefix)
    added = 0
    for entry in files:
        src_path = normalize_path(entry.get("path", ""))
        if not src_path:
            continue
        if not (src_path.startswith("/mail") or src_path.startswith("/logs") or src_path.startswith("/data")):
            continue
        dest_path = normalize_path(prefix + src_path)
        if dest_path in fs:
            continue
        access = entry.get("access", AccessLevel.GUEST)
        try:
            access = AccessLevel(access)
        except Exception:
            access = AccessLevel.GUEST
        content = entry.get("content", "")
        # Ensure parent directories.
        parts = dest_path.strip("/").split("/")
        cur = ""
        for part in parts[:-1]:
            cur = f"{cur}/{part}" if cur else f"/{part}"
            _ensure_dir(fs, cur, access)
        fs[dest_path] = FSNode(path=dest_path, node_type=FSNodeType.FILE, content=content, access=access)
        added += 1
    return added
