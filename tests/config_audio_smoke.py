from __future__ import annotations

from retorno.cli.parser import parse_command
from retorno.model.os import OSState
from retorno.runtime.operator_config import apply_config_value, config_show_lines


def main() -> None:
    assert parse_command("config show") == "CONFIG_SHOW"
    assert parse_command("config set lang es") == ("CONFIG_SET", "lang", "es")
    assert parse_command("config set audio off") == ("CONFIG_SET", "audio", "off")
    assert parse_command("config set ambientsound on") == ("CONFIG_SET", "ambientsound", "on")

    os_state = OSState()
    assert "audio: on" in config_show_lines(os_state)
    assert "ambientsound: on" in config_show_lines(os_state)
    runtime_lines = config_show_lines(os_state, audio_backend="pygame-mixer", audio_runtime_status="ok")
    assert "audio_backend: pygame-mixer" in runtime_lines
    assert "audio_runtime: ok" in runtime_lines

    msg = apply_config_value(os_state, "audio", "off")
    assert msg == "Audio set to off"
    assert os_state.audio.enabled is False

    msg = apply_config_value(os_state, "ambientsound", "off")
    assert msg == "Ambient sound set to off"
    assert os_state.audio.ambient_enabled is False

    msg = apply_config_value(os_state, "lang", "es")
    assert msg == "Idioma cambiado a es"
    assert os_state.locale.value == "es"

    lines = config_show_lines(os_state)
    assert "language: es" in lines
    assert "audio: off" in lines
    assert "ambientsound: off" in lines

    print("CONFIG AUDIO SMOKE PASSED")


if __name__ == "__main__":
    main()
