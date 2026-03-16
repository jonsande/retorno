from __future__ import annotations

from retorno.bootstrap import create_initial_state_prologue
from retorno.config.balance import Balance
from retorno.runtime.data_loader import load_locations
from retorno.worldgen.generator import procedural_radiation_for_node


def _mean(values: list[float]) -> float:
    return sum(values) / max(1, len(values))


def main() -> None:
    seed = Balance.DEFAULT_RNG_SEED

    # 1) Procedural radiation is deterministic and strictly positive.
    sample = procedural_radiation_for_node(seed, "WRECK_AB12CD", "ship", "disk")
    assert sample > 0.0, sample
    assert sample == procedural_radiation_for_node(seed, "WRECK_AB12CD", "ship", "disk")

    # 2) Region ordering should hold statistically: bulge > disk > halo.
    bulge_vals = [
        procedural_radiation_for_node(seed, f"STATION_B_{i:04d}", "station", "bulge")
        for i in range(200)
    ]
    disk_vals = [
        procedural_radiation_for_node(seed, f"STATION_D_{i:04d}", "station", "disk")
        for i in range(200)
    ]
    halo_vals = [
        procedural_radiation_for_node(seed, f"STATION_H_{i:04d}", "station", "halo")
        for i in range(200)
    ]
    assert min(bulge_vals) > 0.0 and min(disk_vals) > 0.0 and min(halo_vals) > 0.0
    assert _mean(bulge_vals) > _mean(disk_vals) > _mean(halo_vals), (
        _mean(bulge_vals),
        _mean(disk_vals),
        _mean(halo_vals),
    )

    # 3) Wrecks (kind=ship) should be hotter than other kinds statistically.
    wreck_vals = [
        procedural_radiation_for_node(seed, f"WRECK_{i:06X}", "ship", "disk")
        for i in range(200)
    ]
    station_vals = [
        procedural_radiation_for_node(seed, f"STATION_{i:06X}", "station", "disk")
        for i in range(200)
    ]
    assert _mean(wreck_vals) > _mean(station_vals), (_mean(wreck_vals), _mean(station_vals))

    # 4) Authored nodes keep explicit configured values (including zero when authored that way).
    state = create_initial_state_prologue()
    assert state.world.space.nodes["UNKNOWN"].radiation_rad_per_s == 0.0005
    authored_cfg = next(
        loc for loc in load_locations() if (loc.get("node", {}) or {}).get("node_id") == "RETORNO_SHIP"
    )
    assert float(authored_cfg["node"]["radiation_rad_per_s"]) == 0.0

    print("PROCEDURAL RADIATION SMOKE PASSED")


if __name__ == "__main__":
    main()
