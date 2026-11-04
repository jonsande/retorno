from __future__ import annotations

import random
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from retorno.bootstrap import create_initial_state_prologue, create_initial_state_sandbox
from retorno.config.balance import Balance
from retorno.core.actions import DroneDeploy, SalvageModule
from retorno.core.engine import Engine
from retorno.io.save_load import load_single_slot, save_single_slot
from retorno.model.drones import DroneStatus
from retorno.model.events import EventType
from retorno.model.galaxy import op_to_galactic_coords
from retorno.model.world import SECTOR_SIZE_LY, region_for_pos
from retorno.runtime.data_loader import load_modules, load_worldgen_templates
from retorno.worldgen.generator import _pick_modules, ensure_sector_generated


# Operational centers map to galactic X=250205, 5, and 410005 ly.
# Keep the same request sequence: disk -> bulge -> halo -> authored origin.
_REGIONS = (
    ("disk", "S+020_+000_+000", (205.0, 5.0, 5.0)),
    ("bulge", "S-25000_+000_+000", (-249995.0, 5.0, 5.0)),
    ("halo", "S+16000_+000_+000", (160005.0, 5.0, 5.0)),
)
_SEEDS = (1, 2)
_COUNTS = {
    1: {"disk": [0, 2, 2], "bulge": [1, 2], "halo": [0]},
    2: {"disk": [0, 1], "bulge": [2, 3], "halo": [1]},
}
_PROFILES = {
    "disk": (0, 2, "common"),
    "bulge": (1, 3, ["tech", "rare"]),
    "halo": (0, 1, ["tech", "rare"]),
}
_SALVAGE_KINDS = {"station", "derelict", "ship", "relay", "waystation"}


def _assert_membership(selected, categories, modules) -> None:
    assert all(mid in modules for mid in selected), selected
    assert all(modules[mid]["pool"] in categories for mid in selected), selected


def _assert_selection() -> None:
    modules = load_modules()
    module_ids = list(modules)
    for pool, categories, minimum, maximum in (
        ("common", {"common"}, 0, 2),
        (["tech", "rare"], {"tech", "rare"}, 1, 3),
        (["tech", "rare"], {"tech", "rare"}, 0, 1),
    ):
        seen_counts = set()
        for seed in range(32):
            rng = random.Random(seed)
            selected = _pick_modules(rng, module_ids, minimum, maximum, pool)
            assert minimum <= len(selected) <= maximum, (seed, pool, selected)
            _assert_membership(selected, categories, modules)
            assert selected == _pick_modules(random.Random(seed), module_ids, minimum, maximum, pool)
            # Candidate order is catalog order, with one count roll and uniform
            # choices with replacement. Common must keep its exact RNG behavior.
            reference = random.Random(seed)
            count = reference.randint(minimum, maximum)
            candidates = [mid for mid in module_ids if modules[mid]["pool"] in categories]
            assert selected == [reference.choice(candidates) for _ in range(count)]
            assert rng.getstate() == reference.getstate()
            seen_counts.add(len(selected))
        assert seen_counts == set(range(minimum, maximum + 1)), (pool, seen_counts)

    # A union does not reweight duplicates or depend on category order.
    for pool in (["rare", "tech"], ["tech", "rare", "tech"], ["tech", "unknown", "rare"]):
        assert _pick_modules(random.Random(7), module_ids, 3, 3, pool) == _pick_modules(
            random.Random(7), module_ids, 3, 3, ["tech", "rare"]
        )
    for pool in ([], "", "unknown", ["unknown"], ["bus_stabilizer"]):
        assert _pick_modules(random.Random(7), module_ids, 1, 3, pool) == [], pool
    for pool in (None, "common", ["tech", "rare"]):
        assert _pick_modules(random.Random(7), [], 1, 3, pool) == []
        assert _pick_modules(random.Random(7), module_ids, 0, 0, pool) == []
    unfiltered = _pick_modules(random.Random(7), module_ids, 3, 3)
    assert len(unfiltered) == 3 and set(unfiltered) <= set(modules)
    assert _pick_modules(random.Random(7), ["bus_stabilizer"], 3, 3, "common") == [
        "bus_stabilizer"
    ] * 3
    assert _pick_modules(random.Random(7), ["nonexistent"], 1, 1, "common") == []


def _generate(seed):
    state = create_initial_state_prologue()
    state.meta.rng_seed = seed
    authored = {nid: asdict(node) for nid, node in state.world.space.nodes.items()}
    for _, sector_id, _ in _REGIONS:
        ensure_sector_generated(state, sector_id)
    ensure_sector_generated(state, "S+000_+000_+000")
    return state, authored


def _assert_regions() -> None:
    modules = load_modules()
    templates = load_worldgen_templates()
    for region, _, center in _REGIONS:
        assert region_for_pos(*center) == region
        assert region_for_pos(*(value - SECTOR_SIZE_LY / 2 for value in center)) == region
        cfg = templates[region]["salvage"]
        assert (cfg["modules_min"], cfg["modules_max"], cfg["modules_pool"]) == _PROFILES[region]
    assert op_to_galactic_coords(*_REGIONS[1][2]) == (5.0, 5.0, 5.0)
    assert op_to_galactic_coords(*_REGIONS[2][2]) == (410005.0, 5.0, 5.0)

    for seed in _SEEDS:
        state, authored = _generate(seed)
        repeat, _ = _generate(seed)
        assert asdict(state.world) == asdict(repeat.world), seed
        for region, sector_id, _ in _REGIONS:
            sector = state.world.sector_states[sector_id]
            assert sector.region == region, sector
            nodes = [state.world.space.nodes[nid] for nid in sector.node_ids]
            assert nodes and all(node.kind in _SALVAGE_KINDS for node in nodes)
            counts = [len(node.salvage_modules_available) for node in nodes]
            assert counts == _COUNTS[seed][region], (seed, region, counts)
            print(f"seed={seed} region={region} sector={sector_id} archetype={sector.archetype} counts={counts}")

        # Check the entire materialized clusters, not only the target sectors.
        for sector in state.world.sector_states.values():
            for nid in sector.node_ids:
                if nid in authored:
                    continue
                node = state.world.space.nodes[nid]
                assert node.region == sector.region
        # Gaussian Z can cross a sector boundary and leave a node outside the
        # recorded XY cluster. Include those nodes too. These fixtures are far
        # from galactic region boundaries, so sector and node profiles agree.
        checked = set(state.world.space.nodes) - set(authored)
        for nid in checked:
            node = state.world.space.nodes[nid]
            assert node.region == region_for_pos(node.x_ly, node.y_ly, node.z_ly)
            minimum, maximum, pool = _PROFILES[node.region]
            categories = {pool} if isinstance(pool, str) else set(pool)
            assert node.kind in _SALVAGE_KINDS
            selected = node.salvage_modules_available
            assert minimum <= len(selected) <= maximum, (seed, nid, selected)
            _assert_membership(selected, categories, modules)

        # Authored nodes can acquire physical links/hub metadata during worldgen;
        # their salvage, coordinates, radiation, and every other field stay intact.
        for nid, before in authored.items():
            after = asdict(state.world.space.nodes[nid])
            for key in before.keys() - {"links", "is_hub", "is_topology_hub"}:
                assert after[key] == before[key], (seed, nid, key)

        # Differential run: changing only the picker output cannot alter any
        # other world field (including scrap, drones, radiation, links or intel).
        with patch("retorno.worldgen.generator._pick_modules", return_value=[]):
            without_modules, _ = _generate(seed)
        descriptor = asdict(state.world)
        for nid in checked:
            descriptor["space"]["nodes"][nid]["salvage_modules_available"] = []
        assert descriptor == asdict(without_modules.world), seed

        with TemporaryDirectory() as tmp_dir:
            slot = Path(tmp_dir) / "modules.dat"
            save_single_slot(state, slot)
            loaded = load_single_slot(slot)
            assert loaded is not None and loaded.source == "primary"
            assert asdict(loaded.state.world) == asdict(state.world)
            # Revisiting generated sectors after load cannot replenish modules.
            for _, sector_id, _ in _REGIONS:
                ensure_sector_generated(loaded.state, sector_id)
            assert asdict(loaded.state.world) == asdict(state.world)


def _assert_salvage() -> None:
    state = create_initial_state_sandbox()
    state.meta.rng_seed = 2
    ensure_sector_generated(state, _REGIONS[1][1])
    node = state.world.space.nodes["DERELICT_36B4F8"]
    before = Counter(node.salvage_modules_available)
    assert sum(before.values()) == 2
    # Stage the ship docked at the real generated node, then use normal actions.
    state.ship.current_node_id = state.world.current_node_id = node.node_id
    state.world.current_pos_ly = (node.x_ly, node.y_ly, node.z_ly)
    state.ship.docked_node_id = node.node_id
    state.world.known_nodes.add(node.node_id)
    state.world.known_contacts.add(node.node_id)
    state.world.visited_nodes.add(node.node_id)
    engine = Engine()
    queued = engine.apply_action(state, DroneDeploy(drone_id="D1", sector_id=node.node_id))
    assert any(event.type == EventType.JOB_QUEUED for event in queued), queued
    engine.tick(state, 30.0)
    assert state.ship.drones["D1"].status == DroneStatus.DEPLOYED
    cargo_before = Counter(state.ship.cargo_modules)
    # Seed 2 naturally misses once and succeeds on the second job; leave the
    # configured find probability, RNG counter, and drone mechanics untouched.
    for attempt in range(1, 3):
        queued = engine.apply_action(state, SalvageModule(drone_id="D1", node_id=node.node_id))
        assert any(event.type == EventType.JOB_QUEUED for event in queued), queued
        events = engine.tick(state, Balance.SALVAGE_MODULE_TIME_S + 1.0)
        found = [event for event in events if event.type == EventType.SALVAGE_MODULE_FOUND]
        if found:
            break
        assert Counter(node.salvage_modules_available) == before
    assert len(found) == 1, [(event.type, event.data) for event in events]
    mid = found[0].data["module_id"]
    _assert_membership([mid], {"tech", "rare"}, load_modules())
    assert before - Counter(node.salvage_modules_available) == Counter([mid])
    assert Counter(state.ship.cargo_modules) - cargo_before == Counter([mid])
    with TemporaryDirectory() as tmp_dir:
        slot = Path(tmp_dir) / "salvaged.dat"
        save_single_slot(state, slot)
        loaded = load_single_slot(slot)
        assert loaded is not None
        assert loaded.state.ship.cargo_modules == state.ship.cargo_modules
        assert loaded.state.world.space.nodes[node.node_id].salvage_modules_available == node.salvage_modules_available
        ensure_sector_generated(loaded.state, _REGIONS[1][1])
        assert loaded.state.world.space.nodes[node.node_id].salvage_modules_available == node.salvage_modules_available
    print(f"seed=2 drone salvage node={node.node_id} module={mid} attempts={attempt}; depletion and cargo persist")


def main() -> None:
    _assert_selection()
    _assert_regions()
    _assert_salvage()
    print("WORLDGEN MODULES POOL SMOKE PASSED")


if __name__ == "__main__":
    main()
