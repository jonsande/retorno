from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class AccessLevel(str, Enum):
    GUEST = "guest"
    MED = "med"
    ENG = "eng"
    OPS = "ops"
    SEC = "sec"
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
    auth_levels: set[str] = field(default_factory=lambda: {"GUEST"})
    locale: Locale = Locale.EN
    debug_enabled: bool = False
    fs: dict[str, FSNode] = field(default_factory=dict)
    mail_received_t: dict[str, float] = field(default_factory=dict)
    mail_received_seq: int = 0
    mail_received_seq_map: dict[str, int] = field(default_factory=dict)


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


def _mail_base_id(path: str) -> str | None:
    path = normalize_path(path)
    if not path.startswith("/mail/inbox/") or not path.endswith(".txt"):
        return None
    name = path.rsplit("/", 1)[-1]
    base = name[:-4]
    if base.endswith(".en") or base.endswith(".es"):
        base = base[:-3]
    return base or None


def register_mail(os_state: OSState, path: str, t: float) -> None:
    base = _mail_base_id(path)
    if not base:
        return
    if base not in os_state.mail_received_seq_map:
        os_state.mail_received_seq += 1
        os_state.mail_received_seq_map[base] = os_state.mail_received_seq
    if base not in os_state.mail_received_t:
        os_state.mail_received_t[base] = float(t)


def _normalize_access(value: AccessLevel | str | None) -> AccessLevel:
    if isinstance(value, AccessLevel):
        return value
    if not value:
        return AccessLevel.GUEST
    if isinstance(value, str):
        raw = value.strip().lower()
        for level in AccessLevel:
            if level.value == raw:
                return level
        for level in AccessLevel:
            if level.value == raw.lower():
                return level
    return AccessLevel.GUEST


def _access_label(value: AccessLevel | str | None) -> str:
    level = _normalize_access(value)
    return level.value.upper()


def _has_access(node: FSNode, auth_levels: set[str]) -> bool:
    required = _access_label(node.access)
    return required in auth_levels


def list_dir(fs: dict[str, FSNode], dir_path: str) -> list[str]:
    dir_path = normalize_path(dir_path)
    if dir_path != "/":
        prefix = dir_path + "/"
    else:
        prefix = "/"
    entries: set[str] = set()
    for path, node in fs.items():
        if not path.startswith(prefix):
            continue
        rest = path[len(prefix):]
        if not rest:
            continue
        name = rest.split("/", 1)[0]
        entries.add(name)
    return sorted(entries)


def read_file(fs: dict[str, FSNode], file_path: str, auth_levels: set[str]) -> str:
    file_path = normalize_path(file_path)
    node = fs.get(file_path)
    if not node:
        raise KeyError(file_path)
    if not _has_access(node, auth_levels):
        raise PermissionError(_access_label(node.access))
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
        access = _normalize_access(entry.get("access", AccessLevel.GUEST))
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


def required_access_label(node: FSNode) -> str:
    return _access_label(node.access)
