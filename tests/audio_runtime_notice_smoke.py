from __future__ import annotations

from retorno.audio.config import load_audio_config
from retorno.audio.manager import AudioManager, _AudioBackend


class _FakeRecoveringBackend(_AudioBackend):
    def __init__(self) -> None:
        self._notice: str | None = None

    def prepare(self, cue) -> None:
        return

    def play(self, cue) -> None:
        self._notice = "[WARN] Audio runtime recovered on fake-backend: stream write failed (boom)"

    def stop_channel(self, channel: str) -> None:
        return

    def stop_all(self) -> None:
        return

    def is_available(self) -> bool:
        return True

    def consume_notice(self) -> str | None:
        notice = self._notice
        self._notice = None
        return notice

    @property
    def name(self) -> str:
        return "fake-backend"


def test_audio_manager_consumes_backend_runtime_notice() -> None:
    config = load_audio_config()
    manager = AudioManager(config, backend=_FakeRecoveringBackend())

    manager.play_startup(audio_enabled=True, startup_context="load_game")
    notice = manager.consume_notice()

    assert notice is not None
    assert "Audio runtime recovered on fake-backend" in notice
    assert manager.consume_notice() is None
