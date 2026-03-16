from retorno.runtime.startup import (
    load_hibernate_start_sequence_lines,
    load_hibernate_wake_sequence_lines,
)


def test_hibernate_start_sequence_assets_exist_for_supported_locales() -> None:
    es_lines = load_hibernate_start_sequence_lines("es")
    en_lines = load_hibernate_start_sequence_lines("en")

    assert es_lines
    assert en_lines
    assert es_lines[0] == "Iniciando secuencia de criogenización"
    assert en_lines[0] == "Cryogenization sequence: INIT"


def test_hibernate_wake_sequence_assets_exist_for_supported_locales() -> None:
    es_normal = load_hibernate_wake_sequence_lines("es", emergency=False)
    en_normal = load_hibernate_wake_sequence_lines("en", emergency=False)
    es_emergency = load_hibernate_wake_sequence_lines("es", emergency=True)
    en_emergency = load_hibernate_wake_sequence_lines("en", emergency=True)

    assert es_normal
    assert en_normal
    assert es_emergency
    assert en_emergency
    assert es_normal[0] == "[core_os] Integridad de programación de despertar: OK"
    assert en_emergency[0] == "[core_os] Wake schedule integrity: OVERRIDDEN"
