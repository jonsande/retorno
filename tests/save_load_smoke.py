from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import pickle

from retorno.bootstrap import create_initial_state_prologue
from retorno.core.engine import Engine
from retorno.core.actions import DroneDeploy
from retorno.io.save_load import (
    SaveLoadError,
    load_single_slot,
    normalize_user_id,
    resolve_save_path,
    save_single_slot,
)


def main() -> None:
    with TemporaryDirectory() as tmp_dir:
        slot_path = Path(tmp_dir) / "slot.dat"

        assert load_single_slot(slot_path) is None, "Expected empty save slot at startup"

        state = create_initial_state_prologue()
        state.clock.t = 1234.5
        state.meta.rng_counter = 77
        state.ship.in_transit = True
        state.ship.arrival_t = 4567.0
        engine = Engine()
        deploy_events = engine.apply_action(state, DroneDeploy(drone_id="D1", sector_id="PWR-A2"))
        assert deploy_events, "Expected deploy job to be queued for save/load test"
        save_single_slot(state, slot_path)

        loaded = load_single_slot(slot_path)
        assert loaded is not None, "Expected save to load from primary slot"
        assert loaded.source == "primary", f"Expected primary source, got {loaded.source}"
        assert loaded.state.clock.t == 1234.5, f"Unexpected clock value: {loaded.state.clock.t}"
        assert loaded.state.meta.rng_counter == 77, f"Unexpected rng_counter: {loaded.state.meta.rng_counter}"
        assert loaded.state.ship.in_transit is True, "Transit flag should persist across save/load"
        assert loaded.state.ship.arrival_t == 4567.0, "Arrival ETA should persist across save/load"
        assert loaded.state.jobs.active_job_ids, "Active jobs should persist across save/load"
        first_job_id = loaded.state.jobs.active_job_ids[0]
        first_job = loaded.state.jobs.jobs[first_job_id]
        assert first_job.eta_s > 0, "Job ETA should persist across save/load"

        loaded.state.clock.t = 2222.0
        save_single_slot(loaded.state, slot_path)
        backup_path = Path(str(slot_path.resolve()) + ".bak")
        assert backup_path.exists(), "Expected backup save file after second save"

        slot_path.write_bytes(b"corrupted-main-save")
        recovered = load_single_slot(slot_path)
        assert recovered is not None, "Expected fallback load from backup"
        assert recovered.source == "backup", f"Expected backup source, got {recovered.source}"
        assert recovered.state.clock.t == 1234.5, "Backup should contain previous snapshot"

        backup_path.write_bytes(b"corrupted-backup-save")
        try:
            load_single_slot(slot_path)
        except SaveLoadError:
            pass
        else:
            raise AssertionError("Expected SaveLoadError when primary and backup are both corrupted")

        # Per-user default slots should resolve to different paths.
        alice_path = resolve_save_path(user="alice")
        bob_path = resolve_save_path(user="bob")
        assert alice_path != bob_path, "User profiles should not share the same default save path"
        assert "/users/alice/" in str(alice_path), "alice path should include user folder"
        assert "/users/bob/" in str(bob_path), "bob path should include user folder"

        # Invalid user ids must fail fast.
        try:
            normalize_user_id("../bad")
        except SaveLoadError:
            pass
        else:
            raise AssertionError("Expected invalid user id to raise SaveLoadError")

        # Legacy V1 save header must fail with explicit incompatibility.
        legacy_path = Path(tmp_dir) / "legacy_v1.dat"
        legacy_blob = pickle.dumps(state, protocol=pickle.HIGHEST_PROTOCOL)
        legacy_checksum = hashlib.sha256(legacy_blob).hexdigest().encode("ascii")
        legacy_path.write_bytes(b"RETORNO_SAVE_V1\n" + legacy_checksum + b"\n" + legacy_blob)
        try:
            load_single_slot(legacy_path)
        except SaveLoadError as exc:
            assert "incompatible" in str(exc).lower(), f"Expected incompatibility message, got: {exc}"
        else:
            raise AssertionError("Expected legacy V1 save load to fail as incompatible")

    print("SAVE/LOAD SMOKE PASSED")


if __name__ == "__main__":
    main()
