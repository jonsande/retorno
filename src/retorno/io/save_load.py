from __future__ import annotations

import hashlib
import os
import pickle
import re
from dataclasses import dataclass
from pathlib import Path

from retorno.core.gamestate import GameState
from retorno.model.ship_layout import apply_retorno_canonical_layout

_SAVE_MAGIC = b"RETORNO_SAVE_V2"
_LEGACY_SAVE_MAGICS = {b"RETORNO_SAVE_V1"}
_DEFAULT_SLOT_FILENAME = "savegame.dat"
_BACKUP_SUFFIX = ".bak"
_USER_RE = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{0,30}[a-z0-9])?$")


class SaveLoadError(RuntimeError):
    pass


@dataclass(slots=True, frozen=True)
class LoadGameResult:
    state: GameState
    source: str  # "primary" | "backup"
    path: Path


def resolve_save_path(save_path: str | Path | None = None, user: str | None = None) -> Path:
    if save_path is not None:
        return Path(save_path).expanduser().resolve()

    env_save_path = os.environ.get("RETORNO_SAVE_PATH", "").strip()
    if env_save_path:
        return Path(env_save_path).expanduser().resolve()

    base_dir = Path.home() / ".retorno"
    env_save_dir = os.environ.get("RETORNO_SAVE_DIR", "").strip()
    if env_save_dir:
        base_dir = Path(env_save_dir).expanduser()

    normalized_user = normalize_user_id(user)
    if normalized_user:
        return (base_dir / "users" / normalized_user / _DEFAULT_SLOT_FILENAME).resolve()

    env_user = normalize_user_id(os.environ.get("RETORNO_USER"))
    if env_user:
        return (base_dir / "users" / env_user / _DEFAULT_SLOT_FILENAME).resolve()

    return (base_dir / _DEFAULT_SLOT_FILENAME).resolve()


def save_exists(save_path: str | Path | None = None, user: str | None = None) -> bool:
    return resolve_save_path(save_path, user=user).exists()


def save_single_slot(state: GameState, save_path: str | Path | None = None, user: str | None = None) -> Path:
    path = resolve_save_path(save_path, user=user)
    payload = _pack_state(state)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    backup_path = _backup_path(path)

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tmp_path.open("wb") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())

        if path.exists():
            os.replace(path, backup_path)
        os.replace(tmp_path, path)
        _fsync_dir(path.parent)
    except OSError as exc:
        raise SaveLoadError(f"Could not save game to {path}: {exc}") from exc
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass

    return path


def load_single_slot(save_path: str | Path | None = None, user: str | None = None) -> LoadGameResult | None:
    path = resolve_save_path(save_path, user=user)
    backup_path = _backup_path(path)

    if not path.exists() and not backup_path.exists():
        return None

    primary_error: Exception | None = None
    if path.exists():
        try:
            state = _load_from_file(path)
            apply_retorno_canonical_layout(state)
            return LoadGameResult(state=state, source="primary", path=path)
        except Exception as exc:  # noqa: BLE001
            primary_error = exc

    if backup_path.exists():
        try:
            state = _load_from_file(backup_path)
            apply_retorno_canonical_layout(state)
            return LoadGameResult(state=state, source="backup", path=backup_path)
        except Exception as backup_error:  # noqa: BLE001
            msg = (
                f"Save slot is unreadable. primary={path} ({primary_error}); "
                f"backup={backup_path} ({backup_error})"
            )
            raise SaveLoadError(msg) from backup_error

    if primary_error is not None:
        raise SaveLoadError(f"Save slot is unreadable: {path} ({primary_error})") from primary_error

    return None


def _pack_state(state: GameState) -> bytes:
    state_blob = pickle.dumps(state, protocol=pickle.HIGHEST_PROTOCOL)
    checksum = hashlib.sha256(state_blob).hexdigest().encode("ascii")
    return _SAVE_MAGIC + b"\n" + checksum + b"\n" + state_blob


def _load_from_file(path: Path) -> GameState:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise SaveLoadError(f"Could not read save file {path}: {exc}") from exc

    first_nl = raw.find(b"\n")
    second_nl = raw.find(b"\n", first_nl + 1) if first_nl != -1 else -1
    if first_nl == -1 or second_nl == -1:
        raise SaveLoadError(f"Malformed save file header: {path}")

    magic = raw[:first_nl]
    checksum = raw[first_nl + 1 : second_nl]
    payload = raw[second_nl + 1 :]

    if magic != _SAVE_MAGIC:
        if magic in _LEGACY_SAVE_MAGICS:
            raise SaveLoadError(
                "Save incompatible with data-pool refactor; start a new game."
            )
        raise SaveLoadError(f"Unknown save format in {path}")

    payload_hash = hashlib.sha256(payload).hexdigest().encode("ascii")
    if payload_hash != checksum:
        raise SaveLoadError(f"Checksum mismatch in {path}")

    try:
        loaded = pickle.loads(payload)
    except Exception as exc:  # noqa: BLE001
        raise SaveLoadError(f"Could not decode save file {path}: {exc}") from exc

    if not isinstance(loaded, GameState):
        raise SaveLoadError(f"Save file {path} does not contain a GameState")
    if int(getattr(loaded.meta, "save_version", 0)) < 2:
        raise SaveLoadError(
            "Save incompatible with data-pool refactor; start a new game."
        )

    return loaded


def _backup_path(path: Path) -> Path:
    return Path(str(path) + _BACKUP_SUFFIX)


def normalize_user_id(user: str | None) -> str | None:
    if user is None:
        return None
    cleaned = user.strip().lower()
    if not cleaned:
        return None
    if not _USER_RE.fullmatch(cleaned):
        raise SaveLoadError(
            "Invalid user id. Use 1-32 chars: a-z, 0-9, '.', '_' or '-', no spaces."
        )
    return cleaned


def _fsync_dir(path: Path) -> None:
    # Best-effort fsync to reduce risk of metadata loss after power failure.
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)
