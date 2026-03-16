from __future__ import annotations

from retorno.model.os import Locale, OSState
from retorno.ui_theme import normalize_theme_preset, theme_presets


CONFIG_SET_VALUES: dict[str, tuple[str, ...]] = {
    "lang": ("en", "es"),
    "verbose": ("on", "off"),
    "audio": ("on", "off"),
    "ambientsound": ("on", "off"),
    "theme": theme_presets(),
}


def config_keys() -> tuple[str, ...]:
    return tuple(CONFIG_SET_VALUES.keys())


def config_value_choices(key: str) -> tuple[str, ...]:
    return CONFIG_SET_VALUES.get(key, ())


def is_valid_config_value(key: str, value: str) -> bool:
    return value in CONFIG_SET_VALUES.get(key, ())


def config_show_lines(
    os_state: OSState,
    *,
    audio_backend: str | None = None,
    audio_runtime_status: str | None = None,
) -> list[str]:
    levels = ", ".join(sorted(os_state.auth_levels))
    lines = [
        f"language: {os_state.locale.value}",
        f"verbose: {_format_toggle(os_state.help_verbose)}",
        f"audio: {_format_toggle(os_state.audio.enabled)}",
        f"theme: {normalize_theme_preset(os_state.theme_preset)}",
    ]
    ambient_line = f"ambientsound: {_format_toggle(os_state.audio.ambient_enabled)}"
    if not os_state.audio.enabled and os_state.audio.ambient_enabled:
        ambient_line += " (inactive while audio=off)"
    lines.append(ambient_line)
    if audio_backend:
        lines.append(f"audio_backend: {audio_backend}")
    if audio_runtime_status:
        lines.append(f"audio_runtime: {audio_runtime_status}")
    lines.append(f"auth: {levels or '(none)'}")
    return lines


def apply_config_value(os_state: OSState, key: str, value: str) -> str:
    key = key.strip().lower()
    value = value.strip().lower()
    locale_before = os_state.locale.value
    if key == "lang":
        os_state.locale = Locale(value)
        locale = os_state.locale.value
        messages = {
            "en": f"Language set to {os_state.locale.value}",
            "es": f"Idioma cambiado a {os_state.locale.value}",
        }
        return messages.get(locale, messages["en"])
    if key == "verbose":
        os_state.help_verbose = value == "on"
        messages = {
            "en": f"Help verbosity set to {_format_toggle(os_state.help_verbose)}",
            "es": f"Verbosidad de help configurada a {_format_toggle(os_state.help_verbose)}",
        }
        return messages.get(locale_before, messages["en"])
    if key == "audio":
        os_state.audio.enabled = value == "on"
        messages = {
            "en": f"Audio set to {_format_toggle(os_state.audio.enabled)}",
            "es": f"Audio configurado a {_format_toggle(os_state.audio.enabled)}",
        }
        return messages.get(locale_before, messages["en"])
    if key == "ambientsound":
        os_state.audio.ambient_enabled = value == "on"
        messages = {
            "en": f"Ambient sound set to {_format_toggle(os_state.audio.ambient_enabled)}",
            "es": f"Sonido ambiente configurado a {_format_toggle(os_state.audio.ambient_enabled)}",
        }
        return messages.get(locale_before, messages["en"])
    if key == "theme":
        os_state.theme_preset = normalize_theme_preset(value)
        messages = {
            "en": f"Theme set to {os_state.theme_preset}",
            "es": f"Tema configurado a {os_state.theme_preset}",
        }
        return messages.get(locale_before, messages["en"])
    raise KeyError(key)


def audio_flags(os_state: OSState) -> tuple[bool, bool]:
    return os_state.audio.enabled, os_state.audio.ambient_enabled


def resolve_help_verbose(os_state: OSState, verbose: bool | None = None) -> bool:
    if verbose is not None:
        return verbose
    return os_state.help_verbose


def _format_toggle(enabled: bool) -> str:
    return "on" if enabled else "off"
