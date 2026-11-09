"""Productive save/load after legitimate recovery invalidation and early radio."""
from copy import deepcopy
from dataclasses import replace
import hashlib
from pathlib import Path
import pickle
from tempfile import TemporaryDirectory
from retorno.model.world import DeadNodeState

from recovery_provenance_smoke import (
    LEGACY, chain, result, rec, radio, save_load, ready, read, at, compile_radio, reject,
)


def first_link(s, plan):
    ready(s)
    assert len(radio.retry_radio_opportunities(s)) == 1
    op = s.world.radio_opportunities[rec._radio_id(plan, 0)]
    read(s, op.path)
    assert plan.captured == plan.consumed == (0,)
    return op


def roundtrip_inactive(s, plan):
    """Compare all ship resources, cooldowns, world/intel/routes and OS files."""
    frozen = deepcopy((s.world, s.ship, s.os, s.clock, s.meta))
    with TemporaryDirectory() as directory:
        slot = Path(directory)/'invalid.dat'
        save_load.save_single_slot(s, slot)
        loaded = save_load.load_single_slot(slot)
        assert loaded.source == 'primary'
        s = loaded.state
        assert (s.world, s.ship, s.os, s.clock, s.meta) == frozen
        plan = s.world.recovery_plans[plan.plan_id]
        assert plan.status == 'invalid' and plan.status not in rec.ACTIVE
        for _ in range(3):
            rec.advance_recovery_plans(s)
            assert radio.retry_radio_opportunities(s) == []
        # Ordinary passive discovery can move its technical search cursor at B;
        # it is not player progress, intel or a recovery cooldown.
        frozen[0].radio_search_cursor = deepcopy(s.world.radio_search_cursor)
        assert (s.world, s.ship, s.os, s.clock, s.meta) == frozen
        save_load.save_single_slot(s, slot)
        assert save_load.load_single_slot(slot).state.world == s.world
    return s, plan


def missing_later_radio(*, deadnode=False):
    s = chain()
    block = 'deadnode:C' if deadnode else 'provenance'
    if deadnode:
        s.world.dead_nodes['C'] = DeadNodeState(dead_since_t=0)
    proposal = rec.select_recovery(s, block, 'C', budget=rec.RecoveryBudget(sectors=0)).proposal
    plan = rec.confirm_recovery(s, proposal)
    first_link(s, plan)
    if deadnode:
        assert s.world.dead_nodes['C'].attempts == 1
    # Controlled withdrawal of an as-yet-unprepared source. The productive
    # catalog compiler keeps its indexes consistent; no transmitter is added.
    entry = s.world.narrative_snapshot['locations'][0]['radio_emitters']['emitters'][1]
    activity = deepcopy(entry['emissions'])
    entry['emissions'] = []
    compile_radio(s.world.manifest_definition, s.world.narrative_snapshot)
    at(s, 'B')
    frozen = deepcopy((s.world.known_links, s.world.intel, s.ship, s.os,
                       s.world.mobility_failsafe_count, s.world.dead_nodes))
    rec.advance_recovery_plans(s)
    assert plan.status == 'invalid' and plan.stage == 0
    assert plan.invalidation[0] == 'sources_unavailable'
    assert len(s.world.radio_opportunities) == 1
    assert (s.world.known_links, s.world.intel, s.ship, s.os,
            s.world.mobility_failsafe_count, s.world.dead_nodes) == frozen
    return s, plan, activity


def test_01_v2_withdrawn_later_source_persists_and_allows_future_search():
    for deadnode in (False, True):
        s, plan, activity = missing_later_radio(deadnode=deadnode)
        s, plan = roundtrip_inactive(s, plan)
        entry = s.world.narrative_snapshot['locations'][0]['radio_emitters']['emitters'][1]
        entry['emissions'] = activity
        compile_radio(s.world.manifest_definition, s.world.narrative_snapshot)
        # Same block, genuinely available new first source at B; old A receipt
        # is not recycled. Restoration is test setup, never a recovery action.
        rec.request_recovery(s, plan.proposal.block, 'C')
        active = [p for p in s.world.recovery_plans.values() if p.status in rec.ACTIVE]
        assert len(active) == 1 and active[0].plan_id != plan.plan_id
        assert active[0].proposal.first_emission_id == 'fixture-B-C'
        assert len(radio.retry_radio_opportunities(s)) == 1
        assert radio.retry_radio_opportunities(s) == []
        if deadnode:
            assert s.world.dead_nodes['C'].attempts == 2
        assert s.world.recovery_plans[plan.plan_id].status == 'invalid'


def test_02_v2_withdrawn_archive_persists_without_injection():
    s = chain(second=False, salvage=True)
    plan = rec.confirm_recovery(s, result(s, 'C').proposal)
    first_link(s, plan)
    location = next(v for v in s.world.narrative_snapshot['locations'] if v['node']['node_id'] == 'B')
    location['fs_files'] = []
    at(s, 'B')
    rec.advance_recovery_plans(s)
    assert plan.status == 'invalid'
    s, _ = roundtrip_inactive(s, plan)
    assert all(not pool.injected_files for pool in s.world.node_pools.values())


def test_03_pre_engines_legacy_boundary_is_rejected_without_rewrite():
    raw = LEGACY.read_bytes()
    reject(lambda: save_load.load_single_slot(LEGACY))
    assert LEGACY.read_bytes() == raw


def test_04_arbitrary_invalid_status_does_not_legalize_corruption():
    for mutate in (
        lambda p: setattr(p, 'status', 'invalid'),
        lambda p: setattr(p, 'stage', 1),
        lambda p: setattr(p, 'consumed', (1,)),
        lambda p: setattr(p, 'captured', (0, 0)),
        lambda p: setattr(p, 'status', 'complete'),
        lambda p: setattr(p, 'version', rec.LEGACY_VERSION),
        lambda p: setattr(p, 'proposal', replace(p.proposal, stage_sources=None)),
        lambda p: setattr(p, 'proposal', replace(p.proposal, stage_sources=(
            p.proposal.stage_sources[0], rec.StageSource('invented', '0'*64)))),
    ):
        s = chain()
        plan = rec.confirm_recovery(s, result(s, 'C').proposal)
        mutate(plan)
        with TemporaryDirectory() as directory:
            slot = Path(directory)/'bad.dat'
            reject(lambda: save_load.save_single_slot(s, slot))
            rec.advance_recovery_plans(s)  # Engine must not certify adulteration.
            reject(lambda: save_load.save_single_slot(s, slot))


def test_05_invalid_checkpoint_still_rejects_bad_save_and_bad_load():
    good, _, _ = missing_later_radio()
    for mutate in (
        lambda s,p: setattr(p, 'stage', 1),
        lambda s,p: setattr(p, 'consumed', ()),
        lambda s,p: setattr(p, 'invalidation', ('stage_unprepared', p.invalidation[1])),
        lambda s,p: setattr(p, 'proposal', replace(p.proposal, stage_sources=None)),
        lambda s,p: setattr(p, 'version', rec.LEGACY_VERSION),
        lambda s,p: s.world.radio_opportunities.clear(),
        lambda s,p: setattr(next(iter(s.world.radio_opportunities.values())), 'status', 'pending'),
    ):
        s = deepcopy(good)
        plan = next(iter(s.world.recovery_plans.values()))
        mutate(s, plan)
        with TemporaryDirectory() as directory:
            slot = Path(directory)/'bad.dat'
            reject(lambda: save_load.save_single_slot(s, slot))
            # Valid envelope/checksum with incoherent semantic content: loading
            # must reject too, without deleting or rewriting the supplied file.
            blob = pickle.dumps(s, protocol=pickle.HIGHEST_PROTOCOL)
            raw = save_load._SAVE_MAGIC+b'\n'+hashlib.sha256(blob).hexdigest().encode()+b'\n'+blob
            slot.write_bytes(raw)
            reject(lambda: save_load.load_single_slot(slot))
            assert slot.read_bytes() == raw


def early_receipt(*, imported):
    s = chain()
    plan = rec.confirm_recovery(s, result(s, 'C').proposal)
    first_link(s, plan)
    at(s, 'B')
    radio.discover_radio_opportunities(s)
    assert len(radio.retry_radio_opportunities(s)) == 1
    op = s.world.radio_opportunities['radio:fixture-B-C']
    assert op.delivery == {'kind': 'declared_radio'}
    if imported:
        read(s, op.path)
    frozen = deepcopy((s.world.known_links, s.world.intel, s.ship, s.os,
                       s.world.mobility_failsafe_count, s.world.dead_nodes, s.world.mobility_hints))
    receipt = deepcopy((op.path, op.received_t, op.received_locale, op.read_t))
    rec.advance_recovery_plans(s)
    assert plan.stage == 1 and plan.captured == (0, 1)
    assert plan.status == ('stage_consumed' if imported else 'active')
    assert len(s.world.radio_opportunities) == 2
    assert (op.path, op.received_t, op.received_locale, op.read_t) == receipt
    assert (s.world.known_links, s.world.intel, s.ship, s.os,
            s.world.mobility_failsafe_count, s.world.dead_nodes, s.world.mobility_hints) == frozen
    assert radio.retry_radio_opportunities(s) == []
    with TemporaryDirectory() as directory:
        slot = Path(directory)/'early.dat'
        save_load.save_single_slot(s, slot)
        s = save_load.load_single_slot(slot).state
        plan = s.world.recovery_plans[plan.plan_id]
        if not imported:
            assert 'C' not in s.world.known_links.get('B', ())
            read(s, op.path)
        assert plan.consumed == (0, 1)
        at(s, 'C')
        rec.advance_recovery_plans(s)
        assert plan.status == 'complete'
        save_load.save_single_slot(s, slot)
        s = save_load.load_single_slot(slot).state
        assert s.world.recovery_plans[plan.plan_id].status == 'complete'
        assert radio.retry_radio_opportunities(s) == []


def test_06_early_received_notice_reuses_receipt_then_requires_read():
    early_receipt(imported=False)


def test_07_early_imported_notice_reuses_known_link_without_new_delivery():
    early_receipt(imported=True)


def test_08_active_v2_slots_before_additive_checkpoint_still_load():
    s = chain()
    plan = rec.confirm_recovery(s, result(s, 'C').proposal)
    original = rec.RecoveryPlan.__getstate__
    def old_slots(p):
        marker, values = original(p)
        values.pop('source_contract', None)
        values.pop('invalidation', None)
        return marker, values
    with TemporaryDirectory() as directory:
        slot = Path(directory)/'old-v2.dat'
        try:
            rec.RecoveryPlan.__getstate__ = old_slots
            save_load.save_single_slot(s, slot)
        finally:
            rec.RecoveryPlan.__getstate__ = original
        loaded = save_load.load_single_slot(slot).state
        assert loaded.world.recovery_plans[plan.plan_id] == plan


def main():
    tests = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith('test_')]
    for name, fn in tests:
        fn()
        print('PASS', name, flush=True)
    print(f'RECOVERY INVALIDATION: {len(tests)} GROUPS PASS')


if __name__ == '__main__':
    main()
