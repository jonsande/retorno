from __future__ import annotations

from retorno.bootstrap import create_initial_state_sandbox
from retorno.core.lore import (
    _assign_piece_to_node,
    _deliver_piece,
    build_lore_context,
    sync_node_pools_for_known_nodes,
)
from retorno.model.world import add_known_link


def main() -> None:
    state = create_initial_state_sandbox()
    sync_node_pools_for_known_nodes(state)

    node_id = "ECHO_7"
    assert node_id in state.world.node_pools, "Expected ECHO_7 node pool"

    mail_piece = {
        "piece_key": "single:smoke_pref_mail",
        "piece_id": "smoke_pref_mail",
        "piece": {
            "single_id": "smoke_pref_mail",
            "preferred_sources": ["mail"],
            "path_template": "/mail/inbox/smoke_pref_mail.{lang}.txt",
            "content_ref_en": "lore/singles/echo_fragment_01.en.txt",
            "content_ref_es": "lore/singles/echo_fragment_01.es.txt",
        },
        "arc_id": "",
        "role": "single",
        "channels": ["salvage_data", "ship_os_mail", "captured_signal"],
    }
    assert _assign_piece_to_node(state, mail_piece, node_id), "Expected placement success for mail preferred source"
    bound = state.world.lore_placements.piece_channel_bindings.get(mail_piece["piece_key"])
    assert bound == "ship_os_mail", f"Expected ship_os_mail, got {bound!r}"

    log_piece = {
        "piece_key": "single:smoke_pref_log",
        "piece_id": "smoke_pref_log",
        "piece": {
            "single_id": "smoke_pref_log",
            "preferred_sources": ["log"],
            "path_template": "/logs/records/smoke_pref_log.{lang}.txt",
            "content_ref_en": "lore/singles/nav_whisper_02.en.txt",
            "content_ref_es": "lore/singles/nav_whisper_02.es.txt",
        },
        "arc_id": "",
        "role": "single",
        "channels": ["uplink_only", "station_broadcast", "salvage_data"],
    }
    assert _assign_piece_to_node(state, log_piece, node_id), "Expected placement success for log preferred source"
    bound = state.world.lore_placements.piece_channel_bindings.get(log_piece["piece_key"])
    assert bound == "salvage_data", f"Expected salvage_data, got {bound!r}"

    left, right = "HARBOR_12", "ARCHIVE_01"
    add_known_link(state.world, left, right, bidirectional=True)
    ctx = build_lore_context(state, node_id)
    primary_piece = {
        "id": "corridor_01_to_archive",
        "kind": "link",
        "line": "LINK: HARBOR_12 -> ARCHIVE_01",
        "confidence": 0.7,
    }
    _deliver_piece(
        state,
        "corridor_01",
        "corridor_01_to_archive",
        primary_piece,
        "uplink_only",
        ctx,
        is_primary=True,
    )
    arc_state = state.world.arc_placements.get("corridor_01", {})
    primary_state = arc_state.get("primary", {})
    discovered = arc_state.get("discovered", set())
    assert bool(primary_state.get("unlocked")), "Expected primary to unlock even when route already existed"
    assert "corridor_01_to_archive" in discovered, "Expected discovered set to include delivered primary id"

    print("LORE CHANNEL PREFERENCE + UPLINK PRIMARY UNLOCK SMOKE PASSED")


if __name__ == "__main__":
    main()
