from __future__ import annotations

import io
from contextlib import redirect_stdout

from retorno.bootstrap import create_initial_state_prologue
from retorno.cli import repl
from retorno.model.os import Locale


def _capture(fn, *args) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        fn(*args)
    return buf.getvalue()


def main() -> None:
    state = create_initial_state_prologue()

    expected_order = [
        "DCK-A1",
        "STS-BAY",
        "LFS-01",
        "PWR-A1",
        "PWR-A2",
        "PRP-R1",
        "BRG-01",
        "SNS-R1",
        "DRN-BAY",
        "CRG-01",
    ]
    assert list(state.ship.sectors.keys()) == expected_order, state.ship.sectors

    state.os.locale = Locale.EN
    out_en = _capture(repl.render_ship_sectors, state)
    for sid in expected_order:
        assert f"- {sid}:" in out_en, out_en
    assert "DCK-A1: Dock / Airlock" in out_en, out_en
    assert "PWR-A2: Power Distribution" in out_en, out_en
    assert "SNS-R1: Sensors Room" in out_en, out_en

    state.os.locale = Locale.ES
    out_es = _capture(repl.render_ship_sectors, state)
    assert "DCK-A1: Darsena / Exclusa" in out_es, out_es
    assert "PWR-A1: Nucleo de Potencia" in out_es, out_es
    assert "SNS-R1: Sala de Sensores" in out_es, out_es

    state.os.locale = Locale.EN
    locate_lfs = _capture(repl.render_locate, state, "life_support")
    assert "ship_sector: LFS-01 (Life Support)" in locate_lfs, locate_lfs
    locate_power = _capture(repl.render_locate, state, "power_core")
    assert "ship_sector: PWR-A1 (Power Core)" in locate_power, locate_power
    locate_sensors = _capture(repl.render_locate, state, "sensors")
    assert "ship_sector: SNS-R1 (Sensors Room)" in locate_sensors, locate_sensors

    diag = _capture(repl.render_diag, state, "life_support")
    assert "location: LFS-01 (Life Support)" in diag, diag

    print("SHIP LAYOUT OUTPUT SMOKE PASSED")


if __name__ == "__main__":
    main()
