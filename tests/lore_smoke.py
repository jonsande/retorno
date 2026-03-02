from __future__ import annotations

from retorno.bootstrap import create_initial_state_prologue
from retorno.config.balance import Balance
from retorno.core.lore import LoreContext, LoreDelivery, maybe_deliver_lore
import retorno.core.lore as lore_mod


def main() -> None:
    state = create_initial_state_prologue()
    ctx = LoreContext(node_id="ECHO_7", region="bulge", dist_from_origin_ly=0.0, year_since_wake=0.0)

    original_p = Balance.LORE_SINGLES_BASE_P
    original_loader = lore_mod.load_singles
    Balance.LORE_SINGLES_BASE_P = 1.0
    lore_mod.load_singles = lambda: [
        {
            "single_id": "SMOKE_SINGLE",
            "weight": 1.0,
            "channels": ["captured_signal"],
            "constraints": {"min_year": 9999},
            "files": [
                {
                    "path_template": "/logs/smoke/single.{lang}.txt",
                    "content_ref_en": "lore/singles/example_unforced_note.en.txt",
                    "content_ref_es": "lore/singles/example_unforced_note.es.txt",
                }
            ],
        }
    ]
    try:
        result = maybe_deliver_lore(state, "uplink", ctx)
    finally:
        lore_mod.load_singles = original_loader
        Balance.LORE_SINGLES_BASE_P = original_p

    assert isinstance(result, LoreDelivery), f"Expected LoreDelivery, got {type(result)!r}"
    assert result.files == [], f"Expected no delivered files, got: {result.files}"
    assert result.events == [], f"Expected no events, got: {result.events}"

    print("LORE SMOKE PASSED")


if __name__ == "__main__":
    main()
