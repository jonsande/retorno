from __future__ import annotations

from types import SimpleNamespace

from retorno.cli.parser import parse_command
from retorno.model.os import OSState
from retorno.runtime.operator_config import apply_config_value, config_show_lines
from retorno.ui_textual import presenter


def main() -> None:
    assert parse_command("config show") == "CONFIG_SHOW"
    assert parse_command("help") == "HELP"
    assert parse_command("help --verbose") == "HELP_VERBOSE"
    assert parse_command("help --no-verbose") == "HELP_NO_VERBOSE"
    assert parse_command("config set lang es") == ("CONFIG_SET", "lang", "es")
    assert parse_command("config set verbose off") == ("CONFIG_SET", "verbose", "off")
    assert parse_command("config set audio off") == ("CONFIG_SET", "audio", "off")
    assert parse_command("config set ambientsound on") == ("CONFIG_SET", "ambientsound", "on")

    os_state = OSState()
    assert "verbose: on" in config_show_lines(os_state)
    assert "audio: on" in config_show_lines(os_state)
    assert "ambientsound: on" in config_show_lines(os_state)
    runtime_lines = config_show_lines(os_state, audio_backend="pygame-mixer", audio_runtime_status="ok")
    assert "audio_backend: pygame-mixer" in runtime_lines
    assert "audio_runtime: ok" in runtime_lines

    msg = apply_config_value(os_state, "verbose", "off")
    assert msg == "Help verbosity set to off"
    assert os_state.help_verbose is False

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
    assert "verbose: off" in lines
    assert "audio: off" in lines
    assert "ambientsound: off" in lines

    state = SimpleNamespace(os=os_state)
    concise_help = presenter.build_help_lines(state)
    assert "Comandos (resumen)" in concise_help
    assert "Commands (summary)" not in concise_help
    assert "  help" in concise_help
    assert "  help --verbose" in concise_help
    assert not any(" - " in line for line in concise_help if line.startswith("  "))

    verbose_help = presenter.build_help_lines(state, verbose=True)
    assert any("help --verbose - muestra comandos con descripciones breves" in line for line in verbose_help)
    assert any("help --no-verbose - muestra comandos sin descripciones" in line for line in verbose_help)
    assert any("config set verbose <on|off> - activa o desactiva la verbosidad por defecto de help" in line for line in verbose_help)

    print("CONFIG AUDIO SMOKE PASSED")


if __name__ == "__main__":
    main()
