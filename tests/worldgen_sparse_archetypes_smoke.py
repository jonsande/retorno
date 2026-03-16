from __future__ import annotations

from retorno.bootstrap import create_initial_state_prologue
from retorno.model.world import SECTOR_SIZE_LY, region_for_pos, sector_id_for_pos
from retorno.runtime.data_loader import load_worldgen_archetypes, load_worldgen_templates
from retorno.worldgen.generator import ensure_sector_generated


_ALL_ARCHETYPES = {"empty", "ruin_field", "relay_corridor", "isolated_station", "graveyard"}


def _parse_sector_id(sector_id: str) -> tuple[int, int, int]:
    sx, sy, sz = sector_id[1:].split("_")
    return int(sx), int(sy), int(sz)


def _sector_center(sector_id: str) -> tuple[float, float, float]:
    sx, sy, sz = _parse_sector_id(sector_id)
    return (
        sx * SECTOR_SIZE_LY + SECTOR_SIZE_LY / 2.0,
        sy * SECTOR_SIZE_LY + SECTOR_SIZE_LY / 2.0,
        sz * SECTOR_SIZE_LY + SECTOR_SIZE_LY / 2.0,
    )


def _neighbor_ring_2d(sector_id: str) -> list[str]:
    sx, sy, sz = _parse_sector_id(sector_id)
    out: list[str] = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            out.append(f"S{sx+dx:+04d}_{sy+dy:+04d}_{sz:+04d}")
    return out


def _find_sector_in_region(region: str, *, min_radius: int = 0) -> str:
    for radius in range(min_radius, 200):
        for sx in range(-radius, radius + 1):
            for sy in range(-radius, radius + 1):
                if max(abs(sx), abs(sy)) != radius:
                    continue
                sector_id = f"S{sx:+04d}_{sy:+04d}_{0:+04d}"
                if region_for_pos(*_sector_center(sector_id)) == region:
                    return sector_id
    raise AssertionError(f"Unable to find sector in region={region}")


def _node_kinds_for_sector(state, sector_id: str) -> list[str]:
    node_ids = state.world.sector_states[sector_id].node_ids
    return sorted(state.world.space.nodes[node_id].kind for node_id in node_ids)


def _sector_descriptor(state, sector_id: str) -> dict:
    sector_state = state.world.sector_states[sector_id]
    nodes = []
    for node_id in sorted(sector_state.node_ids):
        node = state.world.space.nodes[node_id]
        nodes.append(
            (
                node.node_id,
                node.kind,
                round(node.x_ly, 6),
                round(node.y_ly, 6),
                round(node.z_ly, 6),
                bool(node.is_hub),
                bool(node.is_topology_hub),
                tuple(sorted(node.links)),
            )
        )
    return {
        "region": sector_state.region,
        "archetype": sector_state.archetype,
        "node_ids": tuple(sector_state.node_ids),
        "topology_hub_node_id": sector_state.topology_hub_node_id,
        "playable_hub_node_id": sector_state.playable_hub_node_id,
        "internal_link_count": int(sector_state.internal_link_count),
        "intersector_link_count": int(sector_state.intersector_link_count),
        "nodes": tuple(nodes),
    }


def _assert_region_templates() -> None:
    templates = load_worldgen_templates()
    assert templates["disk"]["archetype_weights"] == {
        "empty": 25,
        "ruin_field": 35,
        "relay_corridor": 20,
        "isolated_station": 15,
        "graveyard": 5,
    }
    assert templates["bulge"]["archetype_weights"] == {
        "empty": 30,
        "ruin_field": 30,
        "relay_corridor": 10,
        "isolated_station": 10,
        "graveyard": 20,
    }
    assert templates["halo"]["archetype_weights"] == {
        "empty": 50,
        "ruin_field": 25,
        "relay_corridor": 5,
        "isolated_station": 5,
        "graveyard": 15,
    }


def _assert_archetype_catalog() -> None:
    archetypes = load_worldgen_archetypes()
    assert set(archetypes) >= _ALL_ARCHETYPES
    assert archetypes["empty"]["node_count_min"] == 0
    assert archetypes["empty"]["node_count_max"] == 1
    assert archetypes["empty"]["intersector_link_max"] == 0
    assert archetypes["empty"]["kind_caps"]["station"] == 0
    assert archetypes["relay_corridor"]["kind_caps"]["station"] == 0
    assert archetypes["isolated_station"]["kind_caps"]["relay"] == 0
    assert archetypes["graveyard"]["kind_caps"]["station"] == 0


def _assert_determinism() -> None:
    sector_id = _find_sector_in_region("disk", min_radius=12)
    state_a = create_initial_state_prologue()
    state_b = create_initial_state_prologue()
    ensure_sector_generated(state_a, sector_id)
    ensure_sector_generated(state_b, sector_id)
    assert _sector_descriptor(state_a, sector_id) == _sector_descriptor(state_b, sector_id)


def _assert_origin_guardrail() -> None:
    state = create_initial_state_prologue()
    origin_sector = sector_id_for_pos(0.0, 0.0, 0.0)
    ensure_sector_generated(state, origin_sector)
    neighbor_states = [
        state.world.sector_states[sid]
        for sid in _neighbor_ring_2d(origin_sector)
        if sid != origin_sector and sid in state.world.sector_states
    ]
    assert neighbor_states, "Expected origin cluster neighbors to be materialized"
    assert any(
        sector_state.archetype in {"relay_corridor", "isolated_station"}
        and sector_state.playable_hub_node_id
        for sector_state in neighbor_states
    ), "Expected sparse guardrail to leave one early-progression neighbor near the origin"


def _assert_neighbor_materialization_without_reveal() -> None:
    state = create_initial_state_prologue()
    sector_id = _find_sector_in_region("disk", min_radius=20)
    ensure_sector_generated(state, sector_id)
    ring = _neighbor_ring_2d(sector_id)
    for sid in ring:
        assert sid in state.world.generated_sectors, f"Expected {sid} generated with local cluster"
    leaked = set(state.world.known_nodes) | set(state.world.known_contacts)
    for sid in ring:
        for node_id in state.world.sector_states[sid].node_ids:
            assert node_id not in leaked, f"Neighbor materialization must not auto-reveal {node_id}"


def _assert_sparse_topology_and_caps() -> None:
    state = create_initial_state_prologue()
    center_sector = _find_sector_in_region("disk", min_radius=20)
    csx, csy, csz = _parse_sector_id(center_sector)
    for dx in range(-8, 9):
        for dy in range(-8, 9):
            ensure_sector_generated(state, f"S{csx+dx:+04d}_{csy+dy:+04d}_{csz:+04d}")

    sample_states = [
        sector_state
        for sector_id, sector_state in state.world.sector_states.items()
        if abs(_parse_sector_id(sector_id)[0] - csx) <= 8 and abs(_parse_sector_id(sector_id)[1] - csy) <= 8
    ]
    assert sample_states, "Expected materialized sector sample"

    seen_archetypes = {sector_state.archetype for sector_state in sample_states}
    assert _ALL_ARCHETYPES.issubset(seen_archetypes), (
        f"Expected all archetypes in disk sample, saw {sorted(seen_archetypes)}"
    )

    node_counts = [len(sector_state.node_ids) for sector_state in sample_states]
    assert max(node_counts) <= 3, f"Sparse worldgen exceeded node cap: {max(node_counts)}"
    assert sum(count <= 3 for count in node_counts) == len(node_counts)
    assert sum(node_counts) / len(node_counts) < 2.1, "Expected sparse mean node density"

    inter_counts = [int(sector_state.intersector_link_count) for sector_state in sample_states]
    assert max(inter_counts) <= 2, f"Unexpected intersector count > 2: {max(inter_counts)}"
    assert sum(count <= 1 for count in inter_counts) >= int(len(inter_counts) * 0.75), (
        "Most sectors should have 0-1 intersector links"
    )
    assert any(count == 0 for count in inter_counts), "Expected local dead ends in sparse topology"

    for sector_state in sample_states:
        kinds = _node_kinds_for_sector(state, sector_state.sector_id)
        if sector_state.playable_hub_node_id:
            playable = state.world.space.nodes[sector_state.playable_hub_node_id]
            assert playable.is_hub is True
        if sector_state.topology_hub_node_id:
            topology = state.world.space.nodes[sector_state.topology_hub_node_id]
            assert topology.is_topology_hub is True

        if sector_state.archetype == "empty":
            assert not set(kinds) & {"station", "relay", "waystation"}
            assert sector_state.playable_hub_node_id is None
            assert int(sector_state.intersector_link_count) == 0
        elif sector_state.archetype == "ruin_field":
            assert kinds.count("station") <= 1
            assert kinds.count("relay") <= 1
            assert kinds.count("ship") <= 2
            assert kinds.count("derelict") <= 2
            assert int(sector_state.intersector_link_count) <= 1
        elif sector_state.archetype == "relay_corridor":
            assert "station" not in kinds
            assert kinds.count("relay") <= 1
            assert kinds.count("ship") <= 1
            assert kinds.count("derelict") <= 1
            assert int(sector_state.intersector_link_count) <= 2
        elif sector_state.archetype == "isolated_station":
            assert "relay" not in kinds
            assert kinds.count("station") <= 1
            assert kinds.count("ship") <= 1
            assert kinds.count("derelict") <= 1
            assert int(sector_state.intersector_link_count) <= 1
        elif sector_state.archetype == "graveyard":
            assert "station" not in kinds
            assert "waystation" not in kinds
            assert kinds.count("relay") <= 1
            assert kinds.count("ship") <= 2
            assert kinds.count("derelict") <= 2
            assert int(sector_state.intersector_link_count) <= 1


def main() -> None:
    _assert_region_templates()
    _assert_archetype_catalog()
    _assert_determinism()
    _assert_origin_guardrail()
    _assert_neighbor_materialization_without_reveal()
    _assert_sparse_topology_and_caps()
    print("WORLDGEN SPARSE ARCHETYPES SMOKE PASSED")


if __name__ == "__main__":
    main()
