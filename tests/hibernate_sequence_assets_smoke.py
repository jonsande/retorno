from retorno.runtime.startup import load_hibernate_start_sequence_lines


def test_hibernate_start_sequence_assets_exist_for_supported_locales() -> None:
    es_lines = load_hibernate_start_sequence_lines("es")
    en_lines = load_hibernate_start_sequence_lines("en")

    assert es_lines
    assert en_lines
    assert es_lines[0] == "Iniciando secuencia de criogenización"
    assert en_lines[0] == "Cryogenization sequence: INIT"
