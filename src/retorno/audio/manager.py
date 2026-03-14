from __future__ import annotations

import array
import os
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Iterable

from retorno.audio.config import AudioConfig, AudioCueConfig
from retorno.model.events import Event


@dataclass(slots=True)
class _PlaybackHandle:
    channel: str
    process: subprocess.Popen[bytes]


@dataclass(slots=True)
class _DecodedCue:
    samples: array.array
    frame_count: int
    sample_rate: int
    channels: int


@dataclass(slots=True)
class _Voice:
    channel: str
    cue: AudioCueConfig
    decoded: _DecodedCue
    loop: bool
    position_frames: int = 0


class _AudioBackend:
    def play(self, cue: AudioCueConfig) -> None:
        raise NotImplementedError

    def stop_channel(self, channel: str) -> None:
        raise NotImplementedError

    def stop_all(self) -> None:
        raise NotImplementedError

    def is_available(self) -> bool:
        raise NotImplementedError

    @property
    def name(self) -> str:
        raise NotImplementedError


class AudioPlaybackError(RuntimeError):
    pass


class NullAudioBackend(_AudioBackend):
    def __init__(self, reason: str = "") -> None:
        self.reason = reason

    def play(self, cue: AudioCueConfig) -> None:
        return

    def stop_channel(self, channel: str) -> None:
        return

    def stop_all(self) -> None:
        return

    def is_available(self) -> bool:
        return False

    @property
    def name(self) -> str:
        return "null"


class PygameMixerAudioBackend(_AudioBackend):
    _SAMPLE_RATE = 44100
    _CHANNELS = 2
    _STOP_FADE_MS = 60
    _MIXER_BUFFER = 4096

    def __init__(self) -> None:
        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        try:
            import pygame
        except Exception as exc:
            raise AudioPlaybackError(f"pygame import failed: {exc}") from exc

        self._pygame = pygame
        self._ffmpeg = shutil.which("ffmpeg")
        if not self._ffmpeg:
            raise AudioPlaybackError("ffmpeg not found for pygame PCM decode")
        try:
            if hasattr(pygame.mixer, "pre_init"):
                pygame.mixer.pre_init(
                    frequency=self._SAMPLE_RATE,
                    size=-16,
                    channels=self._CHANNELS,
                    buffer=self._MIXER_BUFFER,
                    allowedchanges=0,
                )
            if not pygame.mixer.get_init():
                pygame.mixer.init(
                    frequency=self._SAMPLE_RATE,
                    size=-16,
                    channels=self._CHANNELS,
                    buffer=self._MIXER_BUFFER,
                    allowedchanges=0,
                )
            pygame.mixer.set_num_channels(16)
        except Exception as exc:
            raise AudioPlaybackError(f"pygame.mixer init failed: {exc}") from exc

        self._sounds: dict[str, object] = {}
        self._channels: dict[str, object] = {
            "ambient": pygame.mixer.Channel(0),
            "startup": pygame.mixer.Channel(1),
        }
        self._next_dynamic_channel = 2

    def play(self, cue: AudioCueConfig) -> None:
        sound = self._sounds.get(cue.cue_id)
        if sound is None:
            sound = self._load_sound(cue)
            self._sounds[cue.cue_id] = sound
        sound.set_volume(float(cue.volume))

        if cue.channel in self._channels:
            channel = self._channels[cue.channel]
        else:
            dynamic_idx = self._next_dynamic_channel
            self._next_dynamic_channel = 2 + ((self._next_dynamic_channel - 1) % 14)
            channel = self._pygame.mixer.Channel(dynamic_idx)
            self._channels[cue.channel] = channel

        if cue.mode == "loop":
            channel.stop()
            channel.play(sound, loops=-1)
        else:
            channel.play(sound)

    def stop_channel(self, channel: str) -> None:
        mixer_channel = self._channels.get(channel)
        if mixer_channel is not None:
            try:
                mixer_channel.fadeout(self._STOP_FADE_MS)
            except Exception:
                mixer_channel.stop()

    def stop_all(self) -> None:
        try:
            self._pygame.mixer.fadeout(self._STOP_FADE_MS)
        except Exception:
            try:
                self._pygame.mixer.stop()
            except Exception:
                pass

    def is_available(self) -> bool:
        return True

    @property
    def name(self) -> str:
        return "pygame-mixer"

    def _load_sound(self, cue: AudioCueConfig):
        command = [
            self._ffmpeg,
            "-v",
            "error",
            "-nostdin",
            "-i",
            str(cue.path),
            "-f",
            "s16le",
            "-acodec",
            "pcm_s16le",
            "-ac",
            str(self._CHANNELS),
            "-ar",
            str(self._SAMPLE_RATE),
            "pipe:1",
        ]
        try:
            raw = subprocess.check_output(command)
        except subprocess.CalledProcessError as exc:
            raise AudioPlaybackError(f"pygame decode failed for {cue.path.name}: {exc}") from exc
        if not raw:
            raise AudioPlaybackError(f"pygame decode returned no audio for {cue.path.name}")
        try:
            return self._pygame.mixer.Sound(buffer=raw)
        except Exception as exc:
            raise AudioPlaybackError(f"pygame sound load failed for {cue.path.name}: {exc}") from exc


class PcmMixerAudioBackend(_AudioBackend):
    _OUTPUT_SAMPLE_RATE = 44100
    _OUTPUT_CHANNELS = 2
    _CHUNK_FRAMES = 2048

    def __init__(self, binary: str, device: str) -> None:
        self._binary = binary
        self._device = device
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._process: subprocess.Popen[bytes] | None = None
        self._voices: dict[str, _Voice] = {}
        self._decoded_cache: dict[str, _DecodedCue] = {}
        self._ephemeral_seq = 0
        self._ensure_process()

    def play(self, cue: AudioCueConfig) -> None:
        decoded = self._decoded_cache.get(cue.cue_id)
        if decoded is None:
            decoded = self._decode_cue(cue)
            self._decoded_cache[cue.cue_id] = decoded
        channel = cue.channel
        if cue.mode == "once":
            channel = f"{cue.channel}#{self._ephemeral_seq}"
            self._ephemeral_seq += 1
        with self._lock:
            if cue.mode == "loop":
                self._voices.pop(channel, None)
            self._voices[channel] = _Voice(
                channel=channel,
                cue=cue,
                decoded=decoded,
                loop=cue.mode == "loop",
            )
        self._ensure_process()

    def stop_channel(self, channel: str) -> None:
        with self._lock:
            self._voices.pop(channel, None)

    def stop_all(self) -> None:
        with self._lock:
            self._voices.clear()
        self._shutdown_process()

    def is_available(self) -> bool:
        return True

    @property
    def name(self) -> str:
        return f"pcm-mixer-{self._device}"

    def _ensure_process(self) -> None:
        if self._process is not None and self._process.poll() is None and self._thread is not None and self._thread.is_alive():
            return
        self._shutdown_process()
        self._stop.clear()
        command = [
            self._binary,
            "-v",
            "error",
            "-nostdin",
            "-f",
            "f32le",
            "-ar",
            str(self._OUTPUT_SAMPLE_RATE),
            "-ac",
            str(self._OUTPUT_CHANNELS),
            "-i",
            "pipe:0",
            "-f",
            self._device,
            "default",
        ]
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            bufsize=0,
            start_new_session=True,
        )
        time.sleep(0.12)
        if process.poll() is not None:
            stderr = b""
            if process.stderr is not None:
                try:
                    stderr = process.stderr.read() or b""
                except Exception:
                    stderr = b""
            detail = stderr.decode("utf-8", errors="replace").strip() or f"exit code {process.returncode}"
            raise AudioPlaybackError(f"pcm-mixer-{self._device} failed: {detail}")
        self._process = process
        self._thread = threading.Thread(target=self._mix_loop, daemon=True)
        self._thread.start()

    def _shutdown_process(self) -> None:
        self._stop.set()
        thread = self._thread
        self._thread = None
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)
        process = self._process
        self._process = None
        if process is None:
            return
        try:
            if process.stdin is not None and not process.stdin.closed:
                process.stdin.close()
        except Exception:
            pass
        if process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=0.5)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass

    def _decode_cue(self, cue: AudioCueConfig) -> _DecodedCue:
        command = [
            self._binary,
            "-v",
            "error",
            "-nostdin",
            "-i",
            str(cue.path),
            "-f",
            "f32le",
            "-acodec",
            "pcm_f32le",
            "-ac",
            str(self._OUTPUT_CHANNELS),
            "-ar",
            str(self._OUTPUT_SAMPLE_RATE),
            "pipe:1",
        ]
        try:
            raw = subprocess.check_output(command)
        except subprocess.CalledProcessError as exc:
            raise AudioPlaybackError(f"decode failed for {cue.path.name}: {exc}") from exc
        samples = array.array("f")
        samples.frombytes(raw)
        frame_count = len(samples) // self._OUTPUT_CHANNELS
        if frame_count <= 0:
            raise AudioPlaybackError(f"decode returned no audio frames for {cue.path.name}")
        return _DecodedCue(
            samples=samples,
            frame_count=frame_count,
            sample_rate=self._OUTPUT_SAMPLE_RATE,
            channels=self._OUTPUT_CHANNELS,
        )

    def _mix_loop(self) -> None:
        chunk_len = self._CHUNK_FRAMES * self._OUTPUT_CHANNELS
        while not self._stop.is_set():
            process = self._process
            if process is None or process.stdin is None or process.poll() is not None:
                return
            with self._lock:
                voices = list(self._voices.values())
            mixed = [0.0] * chunk_len
            finished_channels: list[str] = []
            for voice in voices:
                fade_in_frames = max(0, int(round(voice.cue.fade_in_s * self._OUTPUT_SAMPLE_RATE)))
                fade_out_frames = max(0, int(round(voice.cue.fade_out_s * self._OUTPUT_SAMPLE_RATE)))
                total_frames = voice.decoded.frame_count
                for frame_idx in range(self._CHUNK_FRAMES):
                    if voice.loop:
                        src_frame = (voice.position_frames + frame_idx) % total_frames
                    else:
                        src_frame = voice.position_frames + frame_idx
                        if src_frame >= total_frames:
                            finished_channels.append(voice.channel)
                            break
                    gain = 1.0
                    if fade_in_frames > 0 and src_frame < fade_in_frames:
                        gain *= src_frame / fade_in_frames
                    if not voice.loop and fade_out_frames > 0 and src_frame >= max(0, total_frames - fade_out_frames):
                        remaining = total_frames - src_frame
                        gain *= max(0.0, remaining / fade_out_frames)
                    base = src_frame * self._OUTPUT_CHANNELS
                    out = frame_idx * self._OUTPUT_CHANNELS
                    mixed[out] += voice.decoded.samples[base] * gain
                    mixed[out + 1] += voice.decoded.samples[base + 1] * gain
                voice.position_frames += self._CHUNK_FRAMES
                if voice.loop:
                    voice.position_frames %= total_frames
                elif voice.position_frames >= total_frames:
                    finished_channels.append(voice.channel)
            if finished_channels:
                with self._lock:
                    for channel in finished_channels:
                        self._voices.pop(channel, None)
            for idx, sample in enumerate(mixed):
                if sample > 1.0:
                    mixed[idx] = 1.0
                elif sample < -1.0:
                    mixed[idx] = -1.0
            payload = array.array("f", mixed).tobytes()
            try:
                process.stdin.write(payload)
            except Exception as exc:
                raise AudioPlaybackError(f"pcm mixer stream write failed: {exc}") from exc


class FfplayAudioBackend(_AudioBackend):
    def __init__(self, binary: str) -> None:
        self._binary = binary
        self._handles: dict[str, _PlaybackHandle] = {}
        self._ephemeral_seq = 0

    def play(self, cue: AudioCueConfig) -> None:
        self._reap_finished()
        channel = cue.channel
        if cue.mode == "once":
            channel = f"{cue.channel}#{self._ephemeral_seq}"
            self._ephemeral_seq += 1
        else:
            self.stop_channel(channel)
        command = [
            self._binary,
            "-nodisp",
            "-autoexit",
            "-loglevel",
            "error",
            "-nostats",
            "-vn",
        ]
        audio_filter = _build_audio_filter(cue)
        if audio_filter:
            command.extend(["-af", audio_filter])
        command.append(str(cue.path))
        process = self._launch(command)
        self._handles[channel] = _PlaybackHandle(channel=channel, process=process)

    def stop_channel(self, channel: str) -> None:
        handle = self._handles.pop(channel, None)
        if handle is None:
            return
        self._terminate(handle.process)

    def stop_all(self) -> None:
        handles = list(self._handles.values())
        self._handles.clear()
        for handle in handles:
            self._terminate(handle.process)

    def is_available(self) -> bool:
        return True

    @property
    def name(self) -> str:
        return "ffplay"

    def _reap_finished(self) -> None:
        stale = [channel for channel, handle in self._handles.items() if handle.process.poll() is not None]
        for channel in stale:
            self._handles.pop(channel, None)

    def _terminate(self, process: subprocess.Popen[bytes]) -> None:
        if process.poll() is not None:
            return
        try:
            process.terminate()
            process.wait(timeout=0.5)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass

    def _launch(self, command: list[str]) -> subprocess.Popen[bytes]:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        time.sleep(0.12)
        if process.poll() is not None:
            stderr = b""
            if process.stderr is not None:
                try:
                    stderr = process.stderr.read() or b""
                except Exception:
                    stderr = b""
            detail = stderr.decode("utf-8", errors="replace").strip() or f"exit code {process.returncode}"
            raise AudioPlaybackError(f"ffplay failed: {detail}")
        return process


class FfmpegDeviceAudioBackend(_AudioBackend):
    def __init__(self, binary: str, device: str) -> None:
        self._binary = binary
        self._device = device
        self._handles: dict[str, _PlaybackHandle] = {}
        self._ephemeral_seq = 0

    def play(self, cue: AudioCueConfig) -> None:
        self._reap_finished()
        channel = cue.channel
        if cue.mode == "once":
            channel = f"{cue.channel}#{self._ephemeral_seq}"
            self._ephemeral_seq += 1
        else:
            self.stop_channel(channel)
        command = [
            self._binary,
            "-v",
            "error",
            "-nostdin",
            "-vn",
        ]
        command.extend(["-i", str(cue.path)])
        audio_filter = _build_audio_filter(cue)
        if audio_filter:
            command.extend(["-filter:a", audio_filter])
        command.extend(["-f", self._device])
        command.append("default")
        process = self._launch(command)
        self._handles[channel] = _PlaybackHandle(channel=channel, process=process)

    def stop_channel(self, channel: str) -> None:
        handle = self._handles.pop(channel, None)
        if handle is None:
            return
        self._terminate(handle.process)

    def stop_all(self) -> None:
        handles = list(self._handles.values())
        self._handles.clear()
        for handle in handles:
            self._terminate(handle.process)

    def is_available(self) -> bool:
        return True

    @property
    def name(self) -> str:
        return f"ffmpeg-{self._device}"

    def _reap_finished(self) -> None:
        stale = [channel for channel, handle in self._handles.items() if handle.process.poll() is not None]
        for channel in stale:
            self._handles.pop(channel, None)

    def _terminate(self, process: subprocess.Popen[bytes]) -> None:
        if process.poll() is not None:
            return
        try:
            process.terminate()
            process.wait(timeout=0.5)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass

    def _launch(self, command: list[str]) -> subprocess.Popen[bytes]:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        time.sleep(0.12)
        if process.poll() is not None:
            stderr = b""
            if process.stderr is not None:
                try:
                    stderr = process.stderr.read() or b""
                except Exception:
                    stderr = b""
            detail = stderr.decode("utf-8", errors="replace").strip() or f"exit code {process.returncode}"
            raise AudioPlaybackError(f"ffmpeg-{self._device} failed: {detail}")
        return process


def create_audio_backend(config: AudioConfig) -> _AudioBackend:
    for backend_name in config.preferred_backends:
        try:
            if backend_name == "pygame-mixer":
                return PygameMixerAudioBackend()
            if backend_name == "pcm-mixer-pulse":
                binary = shutil.which("ffmpeg")
                if binary:
                    return PcmMixerAudioBackend(binary, "pulse")
            if backend_name == "pcm-mixer-alsa":
                binary = shutil.which("ffmpeg")
                if binary:
                    return PcmMixerAudioBackend(binary, "alsa")
            if backend_name == "ffmpeg-pulse":
                binary = shutil.which("ffmpeg")
                if binary:
                    return FfmpegDeviceAudioBackend(binary, "pulse")
            if backend_name == "ffmpeg-alsa":
                binary = shutil.which("ffmpeg")
                if binary:
                    return FfmpegDeviceAudioBackend(binary, "alsa")
            if backend_name == "ffplay":
                binary = shutil.which("ffplay")
                if binary:
                    return FfplayAudioBackend(binary)
        except AudioPlaybackError:
            continue
    return NullAudioBackend("No supported audio backend found")


def _build_audio_filter(cue: AudioCueConfig) -> str:
    filters: list[str] = []
    if cue.mode == "loop" and cue.sample_count:
        filters.append(f"aloop=loop=-1:size={cue.sample_count}")
    if cue.fade_in_s > 0.0:
        filters.append(f"afade=t=in:st=0:d={cue.fade_in_s:.3f}")
    if cue.mode == "once" and cue.fade_out_s > 0.0 and cue.duration_s and cue.duration_s > cue.fade_out_s:
        fade_out_start = max(0.0, cue.duration_s - cue.fade_out_s)
        filters.append(f"afade=t=out:st={fade_out_start:.3f}:d={cue.fade_out_s:.3f}")
    if cue.volume != 1.0:
        filters.append(f"volume={cue.volume:.3f}")
    return ",".join(filters)


class AudioManager:
    def __init__(self, config: AudioConfig, backend: _AudioBackend | None = None) -> None:
        self.config = config
        self.backend = backend if backend is not None else create_audio_backend(config)
        self.notice: str | None = None
        if not self.backend.is_available():
            reason = getattr(self.backend, "reason", "") or "backend unavailable"
            self.notice = f"[WARN] Audio backend unavailable: {reason}"
        self._event_last_played: dict[str, float] = {}

    def start(self, audio_enabled: bool, ambient_enabled: bool) -> None:
        self.apply_preferences(audio_enabled, ambient_enabled)

    def play_startup(self, audio_enabled: bool) -> None:
        if not audio_enabled:
            return
        cue_id = self.config.startup_cue_id
        if not cue_id:
            return
        cue = self.config.cues.get(cue_id)
        if cue is None:
            return
        self._safe_play(cue)

    def shutdown(self) -> None:
        self.backend.stop_all()

    def apply_preferences(self, audio_enabled: bool, ambient_enabled: bool) -> None:
        if not audio_enabled:
            self.backend.stop_all()
            return
        ambient_cue_id = self.config.ambient_cue_id
        if not ambient_cue_id:
            return
        if ambient_enabled:
            cue = self.config.cues.get(ambient_cue_id)
            if cue is not None:
                self._safe_play(cue)
        else:
            ambient_channel = self.config.cues[ambient_cue_id].channel
            self.backend.stop_channel(ambient_channel)

    def handle_event_batch(
        self,
        audio_enabled: bool,
        events: Iterable[Event | tuple[str, Event]],
    ) -> None:
        if not audio_enabled:
            return
        now = time.monotonic()
        for item in events:
            event = item[1] if isinstance(item, tuple) else item
            route = self.config.event_routes.get(event.type.value)
            if route is None:
                continue
            last_played = self._event_last_played.get(event.type.value, 0.0)
            if route.cooldown_s > 0.0 and (now - last_played) < route.cooldown_s:
                continue
            cue = self.config.cues.get(route.cue_id)
            if cue is None:
                continue
            self._safe_play(cue)
            self._event_last_played[event.type.value] = now

    def consume_notice(self) -> str | None:
        notice = self.notice
        self.notice = None
        return notice

    def _safe_play(self, cue: AudioCueConfig) -> None:
        try:
            self.backend.play(cue)
        except AudioPlaybackError as exc:
            self.notice = f"[WARN] Audio playback failed on {self.backend.name}: {exc}"
            self.backend.stop_all()
