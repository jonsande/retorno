from __future__ import annotations

import copy
import io
from contextlib import redirect_stdout

from retorno.bootstrap import create_initial_state_sandbox
from retorno.cli import repl
from retorno.model.os import AccessLevel, FSNode, FSNodeType, Locale
from retorno.model.world import sector_id_for_pos
from retorno.worldgen.generator import _parse_sector_id, ensure_sector_generated


IMPORT_PATH = "/data/nav/sector-validation.txt"
CAT_PATH = "/logs/sector-validation.txt"


def _install_file(state, path: str, content: str) -> None:
    state.os.fs[path] = FSNode(
        path=path,
        node_type=FSNodeType.FILE,
        content=content,
        access=AccessLevel.GUEST,
    )


def _world_snapshot(state) -> dict:
    return {
        "generated_sectors": set(state.world.generated_sectors),
        "sector_states": copy.deepcopy(state.world.sector_states),
        "space_nodes": copy.deepcopy(state.world.space.nodes),
        "space_edges": copy.deepcopy(state.world.space.edges),
        "intersector_link_pairs": set(state.world.intersector_link_pairs),
        "sparse_guardrail_done": state.world.sparse_guardrail_done,
        "known_intel": copy.deepcopy(state.world.known_intel),
        "intel": copy.deepcopy(state.world.intel),
        "known_nodes": set(state.world.known_nodes),
        "known_contacts": set(state.world.known_contacts),
        "known_links": copy.deepcopy(state.world.known_links),
        "rng_counter": state.meta.rng_counter,
    }


def _run_intel_import(state, content: str, *, locale: Locale = Locale.EN) -> str:
    state.os.locale = locale
    _install_file(state, IMPORT_PATH, content)
    output = io.StringIO()
    with redirect_stdout(output):
        repl._handle_intel_import(state, IMPORT_PATH)
    return output.getvalue()


def _run_cat_import(state, content: str, *, locale: Locale) -> str:
    state.os.locale = locale
    _install_file(state, CAT_PATH, content)
    output = io.StringIO()
    with redirect_stdout(output):
        repl.render_cat(state, CAT_PATH)
    return output.getvalue()


def _assert_sector_intel_recorded(state, sector_id: str) -> None:
    assert state.world.known_intel.get(sector_id, {}).get("sector") is True
    assert any(
        item.kind == "sector" and item.sector_id == sector_id
        for item in state.world.intel
    )


def _assert_valid_formats_and_lazy_generation() -> None:
    origin_sector = sector_id_for_pos(0.0, 0.0, 0.0)
    assert origin_sector == "S+000_+000_+000"
    assert _parse_sector_id(origin_sector) == (0, 0, 0)

    existing = create_initial_state_sandbox()
    ensure_sector_generated(existing, origin_sector)
    existing_nodes = set(existing.world.space.nodes)
    existing_known_nodes = set(existing.world.known_nodes)
    output = _run_intel_import(existing, f"SECTOR: {origin_sector}\n")
    assert f"(intel) sector known: {origin_sector}" in output
    _assert_sector_intel_recorded(existing, origin_sector)
    assert set(existing.world.space.nodes) == existing_nodes
    assert existing.world.known_nodes == existing_known_nodes

    signed_sector = "S+012_-013_+014"
    assert _parse_sector_id(signed_sector) == (12, -13, 14)
    lazy = create_initial_state_sandbox()
    assert signed_sector not in lazy.world.generated_sectors
    known_before = set(lazy.world.known_nodes)
    _run_intel_import(lazy, f"SECTOR: {signed_sector}\n")
    assert signed_sector in lazy.world.generated_sectors
    _assert_sector_intel_recorded(lazy, signed_sector)
    assert lazy.world.known_nodes == known_before

    wide_sector = sector_id_for_pos(123450.0, -123460.0, 0.0)
    assert wide_sector == "S+12345_-12346_+000"
    assert _parse_sector_id(wide_sector) == (12345, -12346, 0)
    wide = create_initial_state_sandbox()
    assert wide_sector not in wide.world.generated_sectors
    known_before = set(wide.world.known_nodes)
    _run_intel_import(wide, f"SECTOR: {wide_sector}\n")
    assert wide_sector in wide.world.generated_sectors
    _assert_sector_intel_recorded(wide, wide_sector)
    assert wide.world.known_nodes == known_before


def _assert_invalid_formats_are_non_mutating() -> None:
    invalid_sector_ids = [
        "X+000_+000_+000",
        "",
        "S+000_+000",
        "S+000_+000_+000_+000",
        "S+000_TEXT_+000",
        "S+000/+000/+000",
        "S000_+000_+000",
        "S+00_+000_+000",
        "S+000_-000_+000",
        "S+000_+000_+000suffix",
        "s+000_+000_+000",
        "S+000__+000",
    ]
    state = create_initial_state_sandbox()
    state.world.generated_sectors.clear()
    state.world.sector_states.clear()
    state.world.intersector_link_pairs.clear()

    for sector_id in invalid_sector_ids:
        before = _world_snapshot(state)
        output = _run_intel_import(state, f"SECTOR: {sector_id}\n")
        assert _world_snapshot(state) == before, f"invalid SECTOR mutated state: {sector_id!r}"
        visible_id = sector_id or "<empty>"
        assert f"(intel) invalid sector id: {visible_id}" in output, output

        try:
            _parse_sector_id(sector_id)
        except ValueError:
            pass
        else:
            raise AssertionError(f"parser accepted invalid SECTOR: {sector_id!r}")


def _assert_cat_feedback_is_localized() -> None:
    invalid_sector = "NOT_A_SECTOR"
    state = create_initial_state_sandbox()
    before = _world_snapshot(state)
    output = _run_cat_import(
        state,
        f"SECTOR: {invalid_sector}\n",
        locale=Locale.ES,
    )
    assert _world_snapshot(state) == before
    assert f"(intel) identificador de sector no válido: {invalid_sector}" in output


def _assert_valid_lines_survive_invalid_sector() -> None:
    state = create_initial_state_sandbox()
    invalid_sector = "BROKEN_SECTOR"
    valid_node = "VALID_NODE_AFTER_BAD_SECTOR"
    before_generated = set(state.world.generated_sectors)
    output = _run_intel_import(
        state,
        f"SECTOR: {invalid_sector}\nNODE: {valid_node}\n",
    )
    assert f"(intel) invalid sector id: {invalid_sector}" in output
    assert f"(intel) node known: {valid_node}" in output
    assert valid_node in state.world.known_nodes
    assert state.world.generated_sectors == before_generated
    assert invalid_sector not in state.world.known_intel
    assert not any(
        item.kind == "sector" and item.sector_id == invalid_sector
        for item in state.world.intel
    )


def _assert_sector_blocks_bypass_corrupt_recovery() -> None:
    invalid_sector = "X+000_+000_+000"
    valid_node = "VALID_NODE_AFTER_BAD_SECTOR_BLOCK"
    invalid_block = (
        "[INTEL]\n"
        f"SECTOR: {invalid_sector}\n"
        "[/INTEL]\n"
        f"NODE: {valid_node}\n"
    )

    imported = create_initial_state_sandbox()
    before = _world_snapshot(imported)
    output = _run_intel_import(imported, invalid_block, locale=Locale.EN)
    assert imported.meta.rng_counter == before["rng_counter"]
    assert imported.world.generated_sectors == before["generated_sectors"]
    assert imported.world.sector_states == before["sector_states"]
    assert imported.world.space.nodes == before["space_nodes"]
    assert invalid_sector not in imported.world.known_intel
    assert not any(item.sector_id == invalid_sector for item in imported.world.intel)
    assert f"(intel) invalid sector id: {invalid_sector}" in output
    assert f"(intel) node known: {valid_node}" in output
    assert valid_node in imported.world.known_nodes

    catted = create_initial_state_sandbox()
    before = _world_snapshot(catted)
    output = _run_cat_import(catted, invalid_block, locale=Locale.ES)
    assert catted.meta.rng_counter == before["rng_counter"]
    assert catted.world.generated_sectors == before["generated_sectors"]
    assert catted.world.sector_states == before["sector_states"]
    assert catted.world.space.nodes == before["space_nodes"]
    assert invalid_sector not in catted.world.known_intel
    assert not any(item.sector_id == invalid_sector for item in catted.world.intel)
    assert f"(intel) identificador de sector no válido: {invalid_sector}" in output
    assert f"(intel) node known: {valid_node}" in output
    assert valid_node in catted.world.known_nodes

    canonical_sector = "S+021_-022_+023"
    canonical_block = f"[INTEL]\nSECTOR: {canonical_sector}\n[/INTEL]\n"
    for runner, locale in (
        (_run_intel_import, Locale.EN),
        (_run_cat_import, Locale.ES),
    ):
        state = create_initial_state_sandbox()
        rng_before = state.meta.rng_counter
        known_before = set(state.world.known_nodes)
        output = runner(state, canonical_block, locale=locale)
        assert state.meta.rng_counter == rng_before
        assert canonical_sector in state.world.generated_sectors
        _assert_sector_intel_recorded(state, canonical_sector)
        assert state.world.known_nodes == known_before
        assert f"(intel) sector known: {canonical_sector}" in output


def main() -> None:
    _assert_valid_formats_and_lazy_generation()
    _assert_invalid_formats_are_non_mutating()
    _assert_cat_feedback_is_localized()
    _assert_valid_lines_survive_invalid_sector()
    _assert_sector_blocks_bypass_corrupt_recovery()
    print("SECTOR INTEL VALIDATION SMOKE PASSED")


if __name__ == "__main__":
    main()
