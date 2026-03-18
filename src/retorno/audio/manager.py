from __future__ import annotations

import array
import os
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Iterable

from retorno.audio.config import AudioConfig, AudioCueConfig, AudioMusicTrack
from retorno.model.events import Event, EventType, Severity


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
    played_frames_total: int = 0


@dataclass(slots=True, frozen=True)
class AudioMusicStatus:
    track_id: str | None
    title: str | None
    is_playing: bool
    volume: float
    ambient_ducked: bool


class _AudioBackend:
    def prepare(self, cue: AudioCueConfig) -> None:
        return

    def play(self, cue: AudioCueConfig) -> None:
        raise NotImplementedError

    def stop_channel(self, channel: str) -> None:
        raise NotImplementedError

    def stop_all(self) -> None:
        raise NotImplementedError

    def is_available(self) -> bool:
        raise NotImplementedError

    def set_channel_gain(self, channel: str, gain: float) -> None:
        return

    def is_channel_active(self, channel: str) -> bool:
        return False

    def consume_notice(self) -> str | None:
        return None

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

    def set_channel_gain(self, channel: str, gain: float) -> None:
        return

    def is_channel_active(self, channel: str) -> bool:
        return False

    @property
    def name(self) -> str:
        return "null"


class PygameMixerAudioBackend(_AudioBackend):
    _SAMPLE_RATE = 44100
    _CHANNELS = 2
    _STOP_FADE_MS = 60
    _MIXER_BUFFER = 4096
    _FIXED_CHANNEL_ORDER = ("ambient", "startup", "music")

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
            name: pygame.mixer.Channel(idx) for idx, name in enumerate(self._FIXED_CHANNEL_ORDER)
        }
        self._channel_gains: dict[str, float] = {name: 1.0 for name in self._channels}
        self._next_dynamic_channel = len(self._FIXED_CHANNEL_ORDER)

    def play(self, cue: AudioCueConfig) -> None:
        self.prepare(cue)
        sound = self._sounds[cue.cue_id]
        sound.set_volume(float(cue.volume))

        if cue.channel in self._channels:
            channel = self._channels[cue.channel]
        else:
            dynamic_idx = self._next_dynamic_channel
            self._next_dynamic_channel += 1
            if self._next_dynamic_channel >= 16:
                self._next_dynamic_channel = len(self._FIXED_CHANNEL_ORDER)
            channel = self._pygame.mixer.Channel(dynamic_idx)
            self._channels[cue.channel] = channel
        try:
            channel.set_volume(float(self._channel_gains.get(cue.channel, 1.0)))
        except Exception:
            pass

        if cue.mode == "loop" or cue.channel in self._FIXED_CHANNEL_ORDER:
            channel.stop()
            channel.play(sound, loops=-1 if cue.mode == "loop" else 0)
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

    def set_channel_gain(self, channel: str, gain: float) -> None:
        gain = max(0.0, min(float(gain), 1.0))
        self._channel_gains[channel] = gain
        mixer_channel = self._channels.get(channel)
        if mixer_channel is not None:
            try:
                mixer_channel.set_volume(gain)
            except Exception:
                pass

    def is_channel_active(self, channel: str) -> bool:
        mixer_channel = self._channels.get(channel)
        if mixer_channel is None:
            return False
        try:
            return bool(mixer_channel.get_busy())
        except Exception:
            return False

    @property
    def name(self) -> str:
        return "pygame-mixer"

    def prepare(self, cue: AudioCueConfig) -> None:
        if cue.cue_id not in self._sounds:
            self._sounds[cue.cue_id] = self._load_sound(cue)

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
    _PULSE_BUFFER_DURATION_MS = 40
    _FIXED_CHANNELS = {"ambient", "startup", "music"}

    def __init__(self, binary: str, device: str) -> None:
        self._binary = binary
        self._device = device
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._process: subprocess.Popen[bytes] | None = None
        self._voices: dict[str, _Voice] = {}
        self._decoded_cache: dict[str, _DecodedCue] = {}
        self._channel_gains: dict[str, float] = {}
        self._ephemeral_seq = 0
        self._notice: str | None = None
        self._ensure_process()

    def play(self, cue: AudioCueConfig) -> None:
        self.prepare(cue)
        decoded = self._decoded_cache[cue.cue_id]
        channel = cue.channel
        if cue.mode == "once" and cue.channel not in self._FIXED_CHANNELS:
            channel = f"{cue.channel}#{self._ephemeral_seq}"
            self._ephemeral_seq += 1
        with self._lock:
            if cue.mode == "loop" or cue.channel in self._FIXED_CHANNELS:
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

    def set_channel_gain(self, channel: str, gain: float) -> None:
        with self._lock:
            self._channel_gains[channel] = max(0.0, min(float(gain), 1.0))

    def is_channel_active(self, channel: str) -> bool:
        with self._lock:
            return any(voice_channel == channel for voice_channel in self._voices)

    def consume_notice(self) -> str | None:
        with self._lock:
            notice = self._notice
            self._notice = None
        return notice

    @property
    def name(self) -> str:
        return f"pcm-mixer-{self._device}"

    def prepare(self, cue: AudioCueConfig) -> None:
        if cue.cue_id not in self._decoded_cache:
            self._decoded_cache[cue.cue_id] = self._decode_cue(cue)

    def _ensure_process(self) -> None:
        if self._process is not None and self._process.poll() is None and self._thread is not None and self._thread.is_alive():
            return
        self._shutdown_process()
        self._stop.clear()
        process = self._spawn_process()
        self._process = process
        self._thread = threading.Thread(target=self._mix_loop, daemon=True)
        self._thread.start()

    def _spawn_process(self) -> subprocess.Popen[bytes]:
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
        ]
        if self._device == "pulse":
            command.extend(
                [
                    "-buffer_duration",
                    str(self._PULSE_BUFFER_DURATION_MS),
                    "-prebuf",
                    "0",
                    "-minreq",
                    "0",
                    "-stream_name",
                    "retorno",
                ]
            )
        command.append("default")
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
        return process

    def _shutdown_process(self) -> None:
        self._stop.set()
        thread = self._thread
        self._thread = None
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=1.0)
        process = self._process
        self._process = None
        if process is None:
            return
        self._terminate_process(process)

    def _terminate_process(self, process: subprocess.Popen[bytes]) -> None:
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

    def _process_error_detail(self, process: subprocess.Popen[bytes]) -> str:
        stderr = b""
        if process.stderr is not None:
            try:
                stderr = process.stderr.read() or b""
            except Exception:
                stderr = b""
        return stderr.decode("utf-8", errors="replace").strip() or f"exit code {process.returncode}"

    def _set_notice(self, message: str) -> None:
        with self._lock:
            self._notice = message

    def _restart_process_from_runtime_failure(self, detail: str) -> bool:
        failed_process = self._process
        self._process = None
        if failed_process is not None:
            self._terminate_process(failed_process)
        try:
            new_process = self._spawn_process()
        except AudioPlaybackError as exc:
            self._set_notice(
                f"[WARN] Audio runtime failed on {self.name}: {detail}. Restart failed: {exc}"
            )
            return False
        self._process = new_process
        self._set_notice(f"[WARN] Audio runtime recovered on {self.name}: {detail}")
        return True

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
            if process is None or process.stdin is None:
                return
            if process.poll() is not None:
                detail = self._process_error_detail(process)
                if self._stop.is_set() or not self._restart_process_from_runtime_failure(
                    f"output stream lost ({detail})"
                ):
                    return
                continue
            with self._lock:
                voices = list(self._voices.values())
                channel_gains = dict(self._channel_gains)
            mixed = [0.0] * chunk_len
            finished_channels: list[str] = []
            for voice in voices:
                fade_in_frames = max(0, int(round(voice.cue.fade_in_s * self._OUTPUT_SAMPLE_RATE)))
                fade_out_frames = max(0, int(round(voice.cue.fade_out_s * self._OUTPUT_SAMPLE_RATE)))
                total_frames = voice.decoded.frame_count
                loop_crossfade_frames = 0
                if voice.loop:
                    loop_crossfade_frames = max(
                        0, int(round(voice.cue.loop_crossfade_s * self._OUTPUT_SAMPLE_RATE))
                    )
                    if total_frames > 1:
                        loop_crossfade_frames = min(loop_crossfade_frames, max(0, total_frames // 2))
                    else:
                        loop_crossfade_frames = 0
                rendered_frames = 0
                for frame_idx in range(self._CHUNK_FRAMES):
                    if voice.loop:
                        src_frame = voice.position_frames
                    else:
                        src_frame = voice.position_frames + frame_idx
                        if src_frame >= total_frames:
                            finished_channels.append(voice.channel)
                            break
                    gain = 1.0
                    gain *= float(voice.cue.volume)
                    gain *= float(channel_gains.get(voice.channel.split("#", 1)[0], 1.0))
                    if fade_in_frames > 0:
                        if voice.loop:
                            age_frame = voice.played_frames_total + frame_idx
                            if age_frame < fade_in_frames:
                                gain *= age_frame / fade_in_frames
                        elif src_frame < fade_in_frames:
                            gain *= src_frame / fade_in_frames
                    if not voice.loop and fade_out_frames > 0 and src_frame >= max(0, total_frames - fade_out_frames):
                        remaining = total_frames - src_frame
                        gain *= max(0.0, remaining / fade_out_frames)
                    base = src_frame * self._OUTPUT_CHANNELS
                    out = frame_idx * self._OUTPUT_CHANNELS
                    left = voice.decoded.samples[base]
                    right = voice.decoded.samples[base + 1]
                    if voice.loop and loop_crossfade_frames > 0 and src_frame >= (total_frames - loop_crossfade_frames):
                        crossfade_idx = src_frame - (total_frames - loop_crossfade_frames)
                        crossfade_progress = (crossfade_idx + 1) / (loop_crossfade_frames + 1)
                        wrap_frame = min(crossfade_idx, total_frames - 1)
                        wrap_base = wrap_frame * self._OUTPUT_CHANNELS
                        left = (left * (1.0 - crossfade_progress)) + (
                            voice.decoded.samples[wrap_base] * crossfade_progress
                        )
                        right = (right * (1.0 - crossfade_progress)) + (
                            voice.decoded.samples[wrap_base + 1] * crossfade_progress
                        )
                    mixed[out] += left * gain
                    mixed[out + 1] += right * gain
                    rendered_frames += 1
                    if voice.loop:
                        voice.position_frames += 1
                        if voice.position_frames >= total_frames:
                            voice.position_frames = loop_crossfade_frames
                if not voice.loop:
                    voice.position_frames += rendered_frames
                voice.played_frames_total += rendered_frames
                if not voice.loop and voice.position_frames >= total_frames:
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
                if self._stop.is_set() or not self._restart_process_from_runtime_failure(
                    f"stream write failed ({exc})"
                ):
                    return
                continue


class FfplayAudioBackend(_AudioBackend):
    _FIXED_CHANNELS = {"ambient", "startup", "music"}

    def __init__(self, binary: str) -> None:
        self._binary = binary
        self._handles: dict[str, _PlaybackHandle] = {}
        self._ephemeral_seq = 0

    def play(self, cue: AudioCueConfig) -> None:
        self._reap_finished()
        channel = cue.channel
        if cue.mode == "once" and cue.channel not in self._FIXED_CHANNELS:
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

    def is_channel_active(self, channel: str) -> bool:
        self._reap_finished()
        handle = self._handles.get(channel)
        return handle is not None and handle.process.poll() is None

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
    _FIXED_CHANNELS = {"ambient", "startup", "music"}

    def __init__(self, binary: str, device: str) -> None:
        self._binary = binary
        self._device = device
        self._handles: dict[str, _PlaybackHandle] = {}
        self._ephemeral_seq = 0

    def play(self, cue: AudioCueConfig) -> None:
        self._reap_finished()
        channel = cue.channel
        if cue.mode == "once" and cue.channel not in self._FIXED_CHANNELS:
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

    def is_channel_active(self, channel: str) -> bool:
        self._reap_finished()
        handle = self._handles.get(channel)
        return handle is not None and handle.process.poll() is None

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
        if self.config.warnings:
            self.notice = "; ".join(f"[WARN] {warning}" for warning in self.config.warnings[:4])
        if not self.backend.is_available():
            reason = getattr(self.backend, "reason", "") or "backend unavailable"
            backend_notice = f"[WARN] Audio backend unavailable: {reason}"
            self.notice = f"{self.notice}; {backend_notice}" if self.notice else backend_notice
        self._event_last_played: dict[str, float] = {}
        self._music_lock = threading.Lock()
        self._music_tracks = {track.track_id: track for track in self.config.music.tracks}
        self._music_volume = float(self.config.music.default_volume)
        self._music_track_id: str | None = None
        self._ambient_ducked = False
        self._monitor_stop = threading.Event()
        self._monitor_thread = threading.Thread(target=self._monitor_music_state, daemon=True)
        self._monitor_thread.start()
        self._apply_music_channel_gain()
        self._refresh_ambient_ducking()

    def start(
        self,
        audio_enabled: bool,
        ambient_enabled: bool,
        music_volume: float | None = None,
    ) -> None:
        self.apply_music_preferences(music_volume)
        self.apply_preferences(audio_enabled, ambient_enabled)

    def prepare_session(
        self,
        audio_enabled: bool,
        ambient_enabled: bool,
        startup_context: str | None = None,
        music_volume: float | None = None,
    ) -> None:
        self.apply_music_preferences(music_volume)
        if not audio_enabled:
            return
        if ambient_enabled and self.config.ambient_cue_id:
            cue = self.config.cues.get(self.config.ambient_cue_id)
            if cue is not None:
                self._safe_prepare(cue)
        startup_cue_id = self._resolve_startup_cue_id(startup_context)
        if startup_cue_id:
            cue = self.config.cues.get(startup_cue_id)
            if cue is not None:
                self._safe_prepare(cue)

    def play_startup(self, audio_enabled: bool, startup_context: str | None = None) -> None:
        if not audio_enabled:
            return
        cue_id = self._resolve_startup_cue_id(startup_context)
        if not cue_id:
            return
        cue = self.config.cues.get(cue_id)
        if cue is None:
            return
        self._safe_play(cue)

    def shutdown(self) -> None:
        self._monitor_stop.set()
        if self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=0.5)
        self.backend.stop_all()

    def apply_preferences(self, audio_enabled: bool, ambient_enabled: bool) -> None:
        if not audio_enabled:
            self.backend.stop_all()
            with self._music_lock:
                self._music_track_id = None
                self._ambient_ducked = False
            return
        ambient_cue_id = self.config.ambient_cue_id
        if not ambient_cue_id:
            return
        if ambient_enabled:
            cue = self.config.cues.get(ambient_cue_id)
            if cue is not None:
                self._safe_play(cue)
                self._refresh_ambient_ducking()
        else:
            ambient_channel = self.config.cues[ambient_cue_id].channel
            self.backend.stop_channel(ambient_channel)

    def apply_music_preferences(self, music_volume: float | None) -> None:
        with self._music_lock:
            if music_volume in {None, ""}:
                self._music_volume = float(self.config.music.default_volume)
            else:
                self._music_volume = max(0.0, min(float(music_volume), 1.0))
        self._apply_music_channel_gain()

    def list_music_tracks(self) -> tuple[AudioMusicTrack, ...]:
        return self.config.music.tracks

    def play_music(self, audio_enabled: bool, track_id: str) -> AudioMusicTrack | None:
        if not audio_enabled:
            return None
        track = self._music_tracks.get(track_id)
        if track is None:
            return None
        self._apply_music_channel_gain()
        cue = self._music_track_to_cue(track)
        self.backend.stop_channel("music")
        self._safe_play(cue)
        with self._music_lock:
            self._music_track_id = track.track_id
        self._refresh_ambient_ducking()
        return track

    def stop_music(self) -> None:
        self.backend.stop_channel("music")
        with self._music_lock:
            self._music_track_id = None
        self._refresh_ambient_ducking()

    def music_status(self) -> AudioMusicStatus:
        is_playing = self.backend.is_channel_active("music")
        with self._music_lock:
            if not is_playing:
                self._music_track_id = None
            track = self._music_tracks.get(self._music_track_id or "")
            return AudioMusicStatus(
                track_id=track.track_id if track is not None else None,
                title=track.title if track is not None else None,
                is_playing=is_playing,
                volume=self._music_volume,
                ambient_ducked=self._ambient_ducked,
            )

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
            qualifiers = self._event_route_qualifiers(event)
            self._play_event_route(str(event.type.value), qualifiers, now)

    def play_event(
        self,
        audio_enabled: bool,
        event_type: EventType | str,
        severity: Severity | str | None = None,
    ) -> None:
        if not audio_enabled:
            return
        event_key = event_type.value if isinstance(event_type, EventType) else str(event_type)
        qualifiers: list[str] = []
        if severity is not None:
            qualifiers.append(severity.value if isinstance(severity, Severity) else str(severity))
        self._play_event_route(event_key, qualifiers, time.monotonic())

    def consume_notice(self) -> str | None:
        backend_notice = self.backend.consume_notice()
        if backend_notice:
            self.notice = f"{self.notice}; {backend_notice}" if self.notice else backend_notice
        notice = self.notice
        self.notice = None
        return notice

    def _safe_play(self, cue: AudioCueConfig) -> None:
        try:
            self.backend.play(cue)
        except AudioPlaybackError as exc:
            self.notice = f"[WARN] Audio playback failed on {self.backend.name}: {exc}"
            self.backend.stop_all()

    def _safe_prepare(self, cue: AudioCueConfig) -> None:
        try:
            self.backend.prepare(cue)
        except AudioPlaybackError as exc:
            self.notice = f"[WARN] Audio preload failed on {self.backend.name}: {exc}"
            self.backend.stop_all()

    def _play_event_route(self, event_key: str, qualifiers: list[str], now: float) -> None:
        route_key, route = self._resolve_event_route(event_key, qualifiers)
        if route_key is None or route is None:
            return
        last_played = self._event_last_played.get(route_key, 0.0)
        if route.cooldown_s > 0.0 and (now - last_played) < route.cooldown_s:
            return
        cue = self.config.cues.get(route.cue_id)
        if cue is None:
            return
        self._safe_play(cue)
        self._event_last_played[route_key] = now

    def _resolve_event_route(self, event_key: str, qualifiers: list[str]) -> tuple[str | None, object | None]:
        candidates = self._event_route_candidates(event_key, qualifiers)
        for route_key in candidates:
            route = self.config.event_routes.get(route_key)
            if route is not None:
                return route_key, route
        if self.config.default_event_route is not None:
            return "__default_event__", self.config.default_event_route
        return None, None

    def _event_route_candidates(self, event_key: str, qualifiers: list[str]) -> list[str]:
        candidates: list[str] = []
        seen: set[str] = set()
        for qualifier in qualifiers:
            route_key = f"{event_key}:{qualifier}"
            if route_key not in seen:
                candidates.append(route_key)
                seen.add(route_key)
        if event_key not in seen:
            candidates.append(event_key)
        return candidates

    def _event_route_qualifiers(self, event: Event) -> list[str]:
        qualifiers: list[str] = [str(event.severity.value)]
        data = event.data if isinstance(event.data, dict) else {}
        job_type = data.get("job_type")
        if job_type:
            qualifiers.append(str(job_type))
        message_key = data.get("message_key")
        if message_key:
            qualifiers.append(f"message_key:{message_key}")
        reason = data.get("reason")
        if reason:
            qualifiers.append(f"reason:{reason}")
        return qualifiers

    def _resolve_startup_cue_id(self, startup_context: str | None) -> str | None:
        if startup_context == "new_game":
            return self.config.startup_new_game_cue_id or self.config.startup_cue_id
        if startup_context == "load_game":
            return self.config.startup_load_game_cue_id or self.config.startup_cue_id
        return self.config.startup_cue_id

    def _music_track_to_cue(self, track: AudioMusicTrack) -> AudioCueConfig:
        return AudioCueConfig(
            cue_id=f"music:{track.track_id}",
            path=track.path,
            mode="once",
            channel="music",
            volume=1.0,
            duration_s=track.duration_s,
            fade_in_s=self.config.music.fade_in_s,
            fade_out_s=self.config.music.fade_out_s,
        )

    def _apply_music_channel_gain(self) -> None:
        try:
            self.backend.set_channel_gain("music", self._music_volume)
        except Exception:
            return

    def _refresh_ambient_ducking(self) -> None:
        ambient_cue_id = self.config.ambient_cue_id
        if not ambient_cue_id:
            return
        ambient_channel = self.config.cues[ambient_cue_id].channel
        should_duck = self.backend.is_channel_active("music") and self.config.music.ambient_ducking_gain < 1.0
        gain = self.config.music.ambient_ducking_gain if should_duck else 1.0
        try:
            self.backend.set_channel_gain(ambient_channel, gain)
        except Exception:
            return
        with self._music_lock:
            self._ambient_ducked = should_duck

    def _monitor_music_state(self) -> None:
        while not self._monitor_stop.wait(0.1):
            is_playing = self.backend.is_channel_active("music")
            with self._music_lock:
                if not is_playing:
                    self._music_track_id = None
            self._refresh_ambient_ducking()
