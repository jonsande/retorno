from __future__ import annotations

from retorno.bootstrap import create_initial_state_prologue
from retorno.model.world import SECTOR_SIZE_LY, region_for_pos, sector_id_for_pos
from retorno.runtime.data_loader import load_worldgen_archetypes, load_worldgen_templates
from retorno.worldgen.generator import ensure_sector_generated


_ALL_ARCHETYPES = {"empty", "ruin_field", "relay_corridor", "isolated_station", "graveyard"}

_EXPECTED_ARCHETYPE_RULES = {
    "empty": {
        "node_count": (0, 1),
        "kind_caps": {"station": 0, "relay": 0, "waystation": 0, "ship": 1, "derelict": 1},
        "forbidden_kinds": {"station", "relay", "waystation"},
        "intersector_link_max": 0,
    },
    "ruin_field": {
        "node_count": (1, 3),
        "kind_caps": {"station": 1, "relay": 1, "waystation": 0, "ship": 2, "derelict": 3},
        "forbidden_kinds": {"waystation"},
        "intersector_link_max": 1,
    },
    "relay_corridor": {
        "node_count": (2, 3),
        "kind_caps": {"station": 0, "relay": 1, "waystation": 1, "ship": 1, "derelict": 2},
        "forbidden_kinds": {"station"},
        "intersector_link_max": 2,
    },
    "isolated_station": {
        "node_count": (1, 2),
        "kind_caps": {"station": 1, "relay": 0, "waystation": 1, "ship": 1, "derelict": 1},
        "forbidden_kinds": {"relay"},
        "intersector_link_max": 1,
    },
    "graveyard": {
        "node_count": (1, 3),
        "kind_caps": {"station": 0, "relay": 1, "waystation": 0, "ship": 2, "derelict": 2},
        "forbidden_kinds": {"station", "waystation"},
        "intersector_link_max": 1,
    },
}


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
    for archetype, expected in _EXPECTED_ARCHETYPE_RULES.items():
        config = archetypes[archetype]
        assert (config["node_count_min"], config["node_count_max"]) == expected["node_count"]
        assert config["kind_caps"] == expected["kind_caps"]
        assert set(config["forbidden_kinds"]) == expected["forbidden_kinds"]
        assert config["intersector_link_max"] == expected["intersector_link_max"]


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
    assert sum(node_counts) / len(node_counts) < 2.1, "Expected sparse mean node density"

    inter_counts = [int(sector_state.intersector_link_count) for sector_state in sample_states]
    assert max(inter_counts) <= 2, f"Unexpected intersector count > 2: {max(inter_counts)}"
    assert sum(count <= 1 for count in inter_counts) >= int(len(inter_counts) * 0.75), (
        "Most sectors should have 0-1 intersector links"
    )
    assert any(count == 0 for count in inter_counts), "Expected local dead ends in sparse topology"

    archetypes = load_worldgen_archetypes()
    for sector_state in sample_states:
        kinds = _node_kinds_for_sector(state, sector_state.sector_id)
        config = archetypes[sector_state.archetype]
        min_nodes = int(config["node_count_min"])
        max_nodes = int(config["node_count_max"])
        assert min_nodes <= len(kinds) <= max_nodes, (
            sector_state.sector_id,
            sector_state.archetype,
            kinds,
            (min_nodes, max_nodes),
        )

        forbidden = set(config.get("forbidden_kinds", []))
        assert forbidden.isdisjoint(kinds), (sector_state.sector_id, sector_state.archetype, kinds, forbidden)

        caps = config.get("kind_caps", {})
        for kind, cap in caps.items():
            assert kinds.count(kind) <= int(cap), (
                sector_state.sector_id,
                sector_state.archetype,
                kind,
                kinds.count(kind),
                int(cap),
            )

        allowed_kinds = set(config.get("kind_weights", {})) | set(config.get("playable_hub_kind_weights", {}))
        assert set(kinds) <= allowed_kinds, (
            sector_state.sector_id,
            sector_state.archetype,
            kinds,
            allowed_kinds,
        )
        assert int(sector_state.intersector_link_count) <= int(config["intersector_link_max"])

        if sector_state.playable_hub_node_id:
            playable = state.world.space.nodes[sector_state.playable_hub_node_id]
            assert playable.is_hub is True
            assert playable.kind in set(config.get("playable_hub_kind_weights", {}))

        if kinds:
            assert sector_state.topology_hub_node_id is not None
            topology = state.world.space.nodes[sector_state.topology_hub_node_id]
            assert topology.is_topology_hub is True
            for node_id in sector_state.node_ids:
                if node_id == topology.node_id:
                    continue
                node = state.world.space.nodes[node_id]
                assert topology.node_id in node.links, (sector_state.sector_id, node_id, topology.node_id)
                assert node_id in topology.links, (sector_state.sector_id, topology.node_id, node_id)
        else:
            assert sector_state.topology_hub_node_id is None

        if sector_state.archetype == "empty":
            assert sector_state.playable_hub_node_id is None
            assert int(sector_state.intersector_link_count) == 0


def _assert_vertical_distribution_centered() -> None:
    state = create_initial_state_prologue()
    center_sector = _find_sector_in_region("disk", min_radius=20)
    csx, csy, csz = _parse_sector_id(center_sector)
    for dx in range(-8, 9):
        for dy in range(-8, 9):
            ensure_sector_generated(state, f"S{csx+dx:+04d}_{csy+dy:+04d}_{csz:+04d}")

    normalized_offsets: list[float] = []
    for sector_id, sector_state in state.world.sector_states.items():
        sx, sy, sz = _parse_sector_id(sector_id)
        if abs(sx - csx) > 8 or abs(sy - csy) > 8 or sz != csz:
            continue
        sector_origin_z = sz * SECTOR_SIZE_LY
        for node_id in sector_state.node_ids:
            node = state.world.space.nodes[node_id]
            normalized_offsets.append((node.z_ly - sector_origin_z) / SECTOR_SIZE_LY)

    assert normalized_offsets, "Expected sampled nodes for vertical distribution check"
    mean_offset = sum(normalized_offsets) / len(normalized_offsets)
    assert 0.30 <= mean_offset <= 0.70, (
        f"Expected node z positions centered within their sectors, got mean normalized offset {mean_offset:.3f}"
    )


def main() -> None:
    _assert_region_templates()
    _assert_archetype_catalog()
    _assert_determinism()
    _assert_origin_guardrail()
    _assert_neighbor_materialization_without_reveal()
    _assert_sparse_topology_and_caps()
    _assert_vertical_distribution_centered()
    print("WORLDGEN SPARSE ARCHETYPES SMOKE PASSED")


if __name__ == "__main__":
    main()
