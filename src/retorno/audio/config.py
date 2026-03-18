from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


_DATA_ROOT = Path(__file__).resolve().parents[3] / "data"
_DEFAULT_AUDIO_CONFIG_PATH = _DATA_ROOT / "audio_config.json"
_MUSIC_ROOT = _DATA_ROOT / "music"
_MUSIC_EXTENSIONS = {".mp3", ".ogg", ".wav", ".flac", ".m4a", ".aac"}


class AudioConfigError(RuntimeError):
    pass


@dataclass(slots=True, frozen=True)
class AudioCueConfig:
    cue_id: str
    path: Path
    mode: str = "once"
    channel: str = "sfx"
    volume: float = 1.0
    duration_s: float | None = None
    sample_rate: int | None = None
    sample_count: int | None = None
    fade_in_s: float = 0.005
    fade_out_s: float = 0.005
    loop_crossfade_s: float = 0.0


@dataclass(slots=True, frozen=True)
class AudioEventRoute:
    cue_id: str
    cooldown_s: float = 0.0


@dataclass(slots=True, frozen=True)
class AudioMusicTrack:
    track_id: str
    title: str
    path: Path
    duration_s: float | None = None


@dataclass(slots=True, frozen=True)
class AudioMusicConfig:
    default_volume: float = 0.6
    ambient_ducking_gain: float = 0.8
    fade_in_s: float = 0.01
    fade_out_s: float = 0.03
    tracks: tuple[AudioMusicTrack, ...] = ()


@dataclass(slots=True, frozen=True)
class AudioConfig:
    version: int
    preferred_backends: tuple[str, ...] = ("ffplay",)
    ambient_cue_id: str | None = None
    startup_cue_id: str | None = None
    startup_new_game_cue_id: str | None = None
    startup_load_game_cue_id: str | None = None
    cues: dict[str, AudioCueConfig] = field(default_factory=dict)
    event_routes: dict[str, AudioEventRoute] = field(default_factory=dict)
    default_event_route: AudioEventRoute | None = None
    music: AudioMusicConfig = field(default_factory=AudioMusicConfig)
    warnings: tuple[str, ...] = ()


def default_audio_config_path() -> Path:
    return _DEFAULT_AUDIO_CONFIG_PATH


def load_audio_config(path: str | Path | None = None) -> AudioConfig:
    config_path = Path(path) if path is not None else default_audio_config_path()
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise AudioConfigError(f"Could not read audio config {config_path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise AudioConfigError(f"Invalid JSON in audio config {config_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise AudioConfigError(f"Audio config {config_path} must contain a JSON object")
    warnings: list[str] = []

    version = int(raw.get("version", 1) or 1)
    backend_cfg = raw.get("backend", {}) or {}
    preferred_backends_raw = backend_cfg.get("preferred_backends", ["ffplay"])
    if not isinstance(preferred_backends_raw, list) or not preferred_backends_raw:
        raise AudioConfigError("audio.backend.preferred_backends must be a non-empty list")
    preferred_backends = tuple(str(item).strip().lower() for item in preferred_backends_raw if str(item).strip())
    if not preferred_backends:
        raise AudioConfigError("audio.backend.preferred_backends must contain at least one backend name")

    cues_raw = raw.get("cues", {})
    if not isinstance(cues_raw, dict) or not cues_raw:
        raise AudioConfigError("audio.cues must be a non-empty object")

    cues: dict[str, AudioCueConfig] = {}
    for cue_id, entry in cues_raw.items():
        try:
            if not isinstance(entry, dict):
                raise AudioConfigError(f"audio.cues.{cue_id} must be an object")
            rel_path = str(entry.get("path", "")).strip()
            if not rel_path:
                raise AudioConfigError(f"audio.cues.{cue_id}.path is required")
            mode = str(entry.get("mode", "once")).strip().lower() or "once"
            if mode not in {"once", "loop"}:
                raise AudioConfigError(f"audio.cues.{cue_id}.mode must be 'once' or 'loop'")
            channel = str(entry.get("channel", "sfx")).strip().lower() or "sfx"
            volume = _float_value(entry, "volume", 1.0)
            fade_in_s = max(0.0, _float_value(entry, "fade_in_s", 0.005))
            fade_out_s = max(0.0, _float_value(entry, "fade_out_s", 0.005))
            loop_crossfade_s = max(0.0, _float_value(entry, "loop_crossfade_s", 0.0))
            asset_path = (_DATA_ROOT / rel_path).resolve()
            if not asset_path.exists():
                raise AudioConfigError(f"Audio asset not found for cue '{cue_id}': {asset_path}")
            duration_s, sample_rate, sample_count = _probe_audio_asset(asset_path)
            cues[cue_id] = AudioCueConfig(
                cue_id=str(cue_id),
                path=asset_path,
                mode=mode,
                channel=channel,
                volume=max(0.0, min(volume, 1.0)),
                duration_s=duration_s,
                sample_rate=sample_rate,
                sample_count=sample_count,
                fade_in_s=fade_in_s,
                fade_out_s=fade_out_s,
                loop_crossfade_s=loop_crossfade_s if mode == "loop" else 0.0,
            )
        except AudioConfigError as exc:
            warnings.append(str(exc))
            continue

    if not cues:
        raise AudioConfigError("audio.cues did not yield any valid cue entries")

    ambient_raw = raw.get("ambient", {}) or {}
    ambient_cue_id = ambient_raw.get("cue")
    if ambient_cue_id is not None:
        ambient_cue_id = str(ambient_cue_id).strip()
        if ambient_cue_id not in cues:
            warnings.append(f"audio.ambient.cue references unknown cue '{ambient_cue_id}'")
            ambient_cue_id = None
        elif cues[ambient_cue_id].mode != "loop":
            warnings.append("audio.ambient.cue must reference a cue configured in loop mode")
            ambient_cue_id = None

    startup_raw = raw.get("startup", {}) or {}
    startup_cue_id = startup_raw.get("cue")
    if startup_cue_id is not None:
        startup_cue_id = str(startup_cue_id).strip()
        if startup_cue_id not in cues:
            warnings.append(f"audio.startup.cue references unknown cue '{startup_cue_id}'")
            startup_cue_id = None
    startup_new_game_cue_id = startup_raw.get("new_game_cue", startup_cue_id)
    if startup_new_game_cue_id is not None:
        startup_new_game_cue_id = str(startup_new_game_cue_id).strip()
        if startup_new_game_cue_id not in cues:
            warnings.append(
                f"audio.startup.new_game_cue references unknown cue '{startup_new_game_cue_id}'"
            )
            startup_new_game_cue_id = startup_cue_id
    startup_load_game_cue_id = startup_raw.get("load_game_cue", startup_cue_id)
    if startup_load_game_cue_id is not None:
        startup_load_game_cue_id = str(startup_load_game_cue_id).strip()
        if startup_load_game_cue_id not in cues:
            warnings.append(
                f"audio.startup.load_game_cue references unknown cue '{startup_load_game_cue_id}'"
            )
            startup_load_game_cue_id = startup_cue_id

    event_routes_raw = raw.get("events", {}) or {}
    if not isinstance(event_routes_raw, dict):
        raise AudioConfigError("audio.events must be an object")
    event_routes: dict[str, AudioEventRoute] = {}
    for event_key, entry in event_routes_raw.items():
        try:
            if not isinstance(entry, dict):
                raise AudioConfigError(f"audio.events.{event_key} must be an object")
            cue_id = str(entry.get("cue", "")).strip()
            if cue_id not in cues:
                raise AudioConfigError(f"audio.events.{event_key} references unknown cue '{cue_id}'")
            cooldown_s = _float_value(entry, "cooldown_s", 0.0)
            event_routes[str(event_key)] = AudioEventRoute(cue_id=cue_id, cooldown_s=max(0.0, cooldown_s))
        except AudioConfigError as exc:
            warnings.append(str(exc))
            continue

    defaults_raw = raw.get("defaults", {}) or {}
    if not isinstance(defaults_raw, dict):
        raise AudioConfigError("audio.defaults must be an object")
    default_event_route: AudioEventRoute | None = None
    default_event_raw = defaults_raw.get("event")
    if default_event_raw is not None:
        try:
            if not isinstance(default_event_raw, dict):
                raise AudioConfigError("audio.defaults.event must be an object")
            cue_id = str(default_event_raw.get("cue", "")).strip()
            if cue_id not in cues:
                raise AudioConfigError(f"audio.defaults.event references unknown cue '{cue_id}'")
            cooldown_s = _float_value(default_event_raw, "cooldown_s", 0.0)
            default_event_route = AudioEventRoute(cue_id=cue_id, cooldown_s=max(0.0, cooldown_s))
        except AudioConfigError as exc:
            warnings.append(str(exc))
            default_event_route = None

    music = _load_music_config(raw.get("music"), warnings)

    return AudioConfig(
        version=version,
        preferred_backends=preferred_backends,
        ambient_cue_id=ambient_cue_id,
        startup_cue_id=startup_cue_id,
        startup_new_game_cue_id=startup_new_game_cue_id,
        startup_load_game_cue_id=startup_load_game_cue_id,
        cues=cues,
        event_routes=event_routes,
        default_event_route=default_event_route,
        music=music,
        warnings=tuple(warnings),
    )


def _float_value(entry: dict, key: str, default: float) -> float:
    value = entry.get(key, default)
    if value in {None, ""}:
        return float(default)
    try:
        return float(value)
    except Exception as exc:
        raise AudioConfigError(f"audio config field '{key}' must be numeric") from exc


def _probe_audio_asset(path: Path) -> tuple[float | None, int | None, int | None]:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "a:0",
        "-show_entries",
        "stream=sample_rate,duration_ts:format=duration",
        "-of",
        "json",
        str(path),
    ]
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        data = json.loads(result.stdout or "{}")
    except Exception:
        return None, None, None

    duration_s: float | None = None
    sample_rate: int | None = None
    sample_count: int | None = None

    format_info = data.get("format", {})
    if isinstance(format_info, dict):
        raw_duration = format_info.get("duration")
        if raw_duration not in {None, ""}:
            try:
                duration_s = max(0.0, float(raw_duration))
            except Exception:
                duration_s = None

    streams = data.get("streams")
    if isinstance(streams, list) and streams:
        stream = streams[0] if isinstance(streams[0], dict) else {}
        raw_sample_rate = stream.get("sample_rate")
        if raw_sample_rate not in {None, ""}:
            try:
                sample_rate = int(raw_sample_rate)
            except Exception:
                sample_rate = None
        raw_duration_ts = stream.get("duration_ts")
        if raw_duration_ts not in {None, ""}:
            try:
                sample_count = int(raw_duration_ts)
            except Exception:
                sample_count = None

    if sample_count is None and duration_s is not None and sample_rate is not None:
        sample_count = max(1, int(round(duration_s * sample_rate)))

    return duration_s, sample_rate, sample_count


def _load_music_config(raw_music: object, warnings: list[str]) -> AudioMusicConfig:
    default_config = AudioMusicConfig(tracks=_scan_music_tracks(warnings))
    if raw_music is None or raw_music == "":
        return default_config
    if not isinstance(raw_music, dict):
        warnings.append("audio.music must be an object")
        return default_config
    try:
        default_volume = max(0.0, min(_float_value(raw_music, "default_volume", default_config.default_volume), 1.0))
        ambient_ducking_gain = max(
            0.0,
            min(_float_value(raw_music, "ambient_ducking_gain", default_config.ambient_ducking_gain), 1.0),
        )
        fade_in_s = max(0.0, _float_value(raw_music, "fade_in_s", default_config.fade_in_s))
        fade_out_s = max(0.0, _float_value(raw_music, "fade_out_s", default_config.fade_out_s))
    except AudioConfigError as exc:
        warnings.append(str(exc))
        return default_config
    return AudioMusicConfig(
        default_volume=default_volume,
        ambient_ducking_gain=ambient_ducking_gain,
        fade_in_s=fade_in_s,
        fade_out_s=fade_out_s,
        tracks=default_config.tracks,
    )


def _scan_music_tracks(warnings: list[str]) -> tuple[AudioMusicTrack, ...]:
    if not _MUSIC_ROOT.exists() or not _MUSIC_ROOT.is_dir():
        return ()
    tracks: list[AudioMusicTrack] = []
    seen_ids: set[str] = set()
    for path in sorted(_MUSIC_ROOT.iterdir(), key=lambda item: item.name.lower()):
        if not path.is_file() or path.suffix.lower() not in _MUSIC_EXTENSIONS:
            continue
        try:
            duration_s, _, _ = _probe_audio_asset(path)
            track_id = _unique_track_id(_slugify_track_id(path.stem), seen_ids)
            tracks.append(
                AudioMusicTrack(
                    track_id=track_id,
                    title=path.stem,
                    path=path.resolve(),
                    duration_s=duration_s,
                )
            )
        except Exception as exc:
            warnings.append(f"music track skipped '{path.name}': {exc}")
    return tuple(tracks)


def _slugify_track_id(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    return slug or "track"


def _unique_track_id(base: str, seen_ids: set[str]) -> str:
    candidate = base
    counter = 2
    while candidate in seen_ids:
        candidate = f"{base}_{counter}"
        counter += 1
    seen_ids.add(candidate)
    return candidate
