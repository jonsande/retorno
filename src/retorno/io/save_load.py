from __future__ import annotations

import hashlib
import os
import pickle
from dataclasses import dataclass
from pathlib import Path

from retorno.core.gamestate import GameState

_SAVE_MAGIC = b"RETORNO_SAVE_V1"
_DEFAULT_SLOT_FILENAME = "savegame.dat"
_BACKUP_SUFFIX = ".bak"


class SaveLoadError(RuntimeError):
    pass


@dataclass(slots=True, frozen=True)
class LoadGameResult:
    state: GameState
    source: str  # "primary" | "backup"
    path: Path


def resolve_save_path(save_path: str | Path | None = None) -> Path:
    if save_path is not None:
        return Path(save_path).expanduser().resolve()

    env_save_path = os.environ.get("RETORNO_SAVE_PATH", "").strip()
    if env_save_path:
        return Path(env_save_path).expanduser().resolve()

    env_save_dir = os.environ.get("RETORNO_SAVE_DIR", "").strip()
    if env_save_dir:
        return (Path(env_save_dir).expanduser() / _DEFAULT_SLOT_FILENAME).resolve()

    return (Path.home() / ".retorno" / _DEFAULT_SLOT_FILENAME).resolve()


def save_exists(save_path: str | Path | None = None) -> bool:
    return resolve_save_path(save_path).exists()


def save_single_slot(state: GameState, save_path: str | Path | None = None) -> Path:
    path = resolve_save_path(save_path)
    payload = _pack_state(state)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    backup_path = _backup_path(path)

    path.parent.mkdir(parents=True, exist_ok=True)
    try:
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


def load_single_slot(save_path: str | Path | None = None) -> LoadGameResult | None:
    path = resolve_save_path(save_path)
    backup_path = _backup_path(path)

    if not path.exists() and not backup_path.exists():
        return None

    primary_error: Exception | None = None
    if path.exists():
        try:
            state = _load_from_file(path)
            return LoadGameResult(state=state, source="primary", path=path)
        except Exception as exc:  # noqa: BLE001
            primary_error = exc

    if backup_path.exists():
        try:
            state = _load_from_file(backup_path)
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

    return loaded


def _backup_path(path: Path) -> Path:
    return Path(str(path) + _BACKUP_SUFFIX)


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
