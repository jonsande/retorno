"""C3B2: successive paid recoveries through the productive physical engine."""
from dataclasses import replace
from hashlib import sha256
import pickle
from unittest.mock import patch

import pytest

from retorno.core.engine import Engine
from retorno.core.nav_recovery import plan_inertial_recovery
from retorno.model.events import EventType
from retorno.runtime.loop import GameLoop
from tests.test_nav_engine_repair_inertia import enqueue_repair
from tests.test_nav_engine_safety_brake import save_and_load, wear_cut
from tests.test_nav_engine_second_inertia_repair import second_inertia
from tests.test_nav_engine_third_recovery import repaired_second


def _assert_lineage(lineage, attempts, interruptions, spent, authorization_id):
    assert lineage.attempt_count == attempts
    assert lineage.interruption_count == interruptions
    assert lineage.capsules_spent == pytest.approx(spent)
    assert lineage.spent_through_authorization_id == authorization_id
    assert len(lineage.recent) <= 2
    digest = lineage.prefix_digest
    for record in lineage.recent:
        digest = sha256((digest + "|" + repr(record)).encode()).hexdigest()
    assert lineage.digest == digest
    assert len(pickle.dumps(lineage)) < 4000


def test_five_successive_manual_payments_with_coast_and_brake_cuts_then_stop():
    game = save_and_load(repaired_second("coast"))
    engine = Engine()
    game.ship.antimatter_capsules = 1000
    game.ship.cargo_scrap = 1000
    original_destination = game.ship.physical_transit.original_destination_id
    original_node = game.world.current_node_id
    original_nodes = set(game.world.space.nodes)
    initial = game.ship.physical_transit.recovery_coast_interruption
    assert initial is not None
    spent = initial.execution.authorization.capsules_paid
    previous_clock = game.clock.t
    previous_distance = game.ship.physical_transit.motion.distance_m
    previous_id = game.ship.physical_transit.recovery_intent.attempt_id
    last_demonstrated = abs(
        game.ship.physical_transit.inertial_continuation.interrupted_segment
        .proper_acceleration_m_s2)

    for number in range(1, 6):
        before_fuel = game.ship.antimatter_capsules
        old_evidence = game.ship.physical_transit.second_repair_evidence
        assert old_evidence is not None
        intent = engine.authorize_manual_inertial_recovery(game, max_capsules=1000)
        if number == 4:
            cancelled_id = intent.attempt_id
            engine.cancel_manual_inertial_recovery(game)
            assert game.ship.physical_transit.second_repair_evidence == old_evidence
            intent = engine.authorize_manual_inertial_recovery(
                game, max_capsules=1000)
            assert intent.attempt_id > cancelled_id
        assert intent.attempt_id > previous_id
        assert intent.paid_predecessor_id == previous_id
        assert game.ship.antimatter_capsules == before_fuel
        game = save_and_load(game)
        plan = plan_inertial_recovery(game)
        assert plan.decision in {"coast_then_brake", "emergency_brake", "brake_now"}
        assert abs(plan.braking_segment.proper_acceleration_m_s2) == last_demonstrated
        if number in {3, 4}:
            excessive = last_demonstrated * 1.01
            excessive_plan = plan_inertial_recovery(
                game, proper_deceleration_m_s2=excessive)
            before_rejection = pickle.dumps(game)
            with pytest.raises(RuntimeError, match="verified physical capacity"):
                engine.prepare_inertial_recovery(
                    game, excessive_plan,
                    proper_deceleration_m_s2=excessive)
            assert pickle.dumps(game) == before_rejection
        physical = engine.prepare_inertial_recovery(game, plan)
        price = physical.recovery_execution.authorization.capsules_paid
        spent += price
        assert game.ship.antimatter_capsules == pytest.approx(before_fuel - price)
        assert physical.second_repair_evidence is None
        assert physical.original_destination_id == original_destination
        _assert_lineage(physical.recovery_lineage, number + 1, number, spent,
                        intent.attempt_id)
        previous_id = intent.attempt_id
        game = save_and_load(game)
        assert game.ship.antimatter_capsules == pytest.approx(before_fuel - price)

        if number == 5:
            game.ship.systems["engines"].base_decay_per_s = 0
            terminal = plan.braking_segment
            for segment in plan.segments:
                due = (segment.start.galactic_s
                       + segment.duration_galactic_s - game.clock.t)
                GameLoop(engine, game).step(due)
            assert game.ship.physical_transit is None
            assert terminal.end_beta == 0
            assert game.ship.antimatter_capsules == pytest.approx(before_fuel - price)
            game = save_and_load(game)
            assert game.ship.physical_transit is None
            assert game.world.current_node_id == game.world.active_tmp_node_id
            assert game.world.current_node_id != original_node
            assert set(game.world.space.nodes) == original_nodes | {game.world.current_node_id}
            assert not any(event.type == EventType.ARRIVED for event in game.events.recent)
            break

        if number <= 2:
            assert len(plan.segments) == 2
            cut_motion = game.ship.physical_transit.motion
            game.ship.systems["engines"].health = .15
            game.ship.systems["engines"].base_decay_per_s = .001
            engine.tick(game, 1)
            physical = game.ship.physical_transit
            assert physical.recovery_coast_interruption.cut_motion == cut_motion
            assert physical.motion.beta == cut_motion.beta
            assert physical.motion.distance_m > cut_motion.distance_m
            assert physical.inertial_continuation is not None
            assert abs(physical.inertial_continuation.interrupted_segment
                       .proper_acceleration_m_s2) == last_demonstrated
        else:
            if len(plan.segments) == 2:
                game.ship.systems["engines"].base_decay_per_s = 0
                engine.tick(game, plan.coast_segment.duration_galactic_s)
            game.ship.systems["engines"].health = .15001
            game.ship.systems["engines"].base_decay_per_s = .001
            cut = wear_cut(game, .15)
            assert cut is not None
            engine.tick(game, cut)
            physical = game.ship.physical_transit
            assert physical.recovery_interruption.cut_motion == physical.motion
            cut_motion = physical.motion
            engine.tick(game, 1)
            physical = game.ship.physical_transit
            assert physical.motion.beta == cut_motion.beta
            assert physical.motion.distance_m > cut_motion.distance_m
            last_demonstrated = abs(
                physical.inertial_continuation.interrupted_segment
                .proper_acceleration_m_s2)

        assert game.clock.t == physical.motion.galactic_s > previous_clock
        assert game.clock.ship_elapsed_s == physical.motion.proper_s
        assert physical.motion.distance_m > previous_distance
        assert physical.original_destination_id == original_destination
        assert physical.second_repair_evidence is None
        assert game.ship.antimatter_capsules == pytest.approx(before_fuel - price)
        assert physical.recovery_lineage.recent[-1].outcome.startswith("interrupted")
        _assert_lineage(physical.recovery_lineage, number + 1, number + 1,
                        spent, intent.attempt_id)
        with pytest.raises(ValueError, match="another interruption"):
            replace(physical, second_repair_evidence=old_evidence)
        game = save_and_load(game)
        no_repair = pickle.dumps(game)
        with pytest.raises(RuntimeError, match="repair after its current cut"):
            engine.authorize_manual_inertial_recovery(game, max_capsules=1000)
        assert pickle.dumps(game) == no_repair

        job = enqueue_repair(game)
        GameLoop(engine, game).step(job.eta_s)
        physical = game.ship.physical_transit
        assert physical.second_repair_evidence.job_internal_id == job.internal_id
        assert physical.second_repair_evidence.cut_motion == cut_motion
        assert physical.motion.beta == cut_motion.beta
        assert game.ship.antimatter_capsules == pytest.approx(before_fuel - price)
        assert len(pickle.dumps(physical)) < 15000
        game = save_and_load(game)
        assert game.ship.physical_transit.second_repair_evidence == physical.second_repair_evidence
        previous_clock = game.clock.t
        previous_distance = game.ship.physical_transit.motion.distance_m

    assert sum(event.type == EventType.PHYSICAL_STOPPED for event in game.events.recent) == 1


@pytest.mark.parametrize("origin", ["brake", "coast"])
def test_zero_eta_repair_is_witnessed_after_current_cut(origin):
    game = second_inertia(origin, activate=False)
    source = (game.ship.physical_transit.recovery_interruption
              or game.ship.physical_transit.recovery_coast_interruption)
    job = enqueue_repair(game)
    game.jobs.jobs[job.internal_id].eta_s = 0.0
    Engine().tick(game, 1)
    evidence = game.ship.physical_transit.second_repair_evidence
    assert evidence is not None
    assert evidence.cut_motion == source.cut_motion
    assert evidence.completed_galactic_s == source.cut_motion.galactic_s
    assert evidence.job_internal_id == job.internal_id
    assert game.ship.physical_transit.inertial_continuation is not None
    game = save_and_load(game)
    assert Engine().authorize_manual_inertial_recovery(
        game, max_capsules=100).status == "pending"


def test_provisional_repair_and_evidence_roll_back_with_later_boundary():
    game = second_inertia("brake")
    job = enqueue_repair(game)
    game.world.lore_placements.next_non_forced_eval_t = game.clock.t + job.eta_s + 1
    before = pickle.dumps(game)
    witnessed = []
    original = Engine._record_recovery_repair_evidence

    def observe_resolution(staged, resolved_ids, health_before):
        original(staged, resolved_ids, health_before)
        evidence = staged.ship.physical_transit.second_repair_evidence
        if evidence is not None:
            witnessed.append(evidence)

    with patch.object(Engine, "_record_recovery_repair_evidence",
                      staticmethod(observe_resolution)):
        with pytest.raises(RuntimeError):
            Engine().tick(game, job.eta_s + 2)
    assert len(witnessed) == 1
    assert witnessed[0].job_internal_id == job.internal_id
    assert pickle.dumps(game) == before
    assert game.ship.physical_transit.second_repair_evidence is None


def test_pending_manual_intent_without_current_evidence_cannot_pay():
    game = repaired_second("brake")
    engine = Engine()
    engine.authorize_manual_inertial_recovery(game, max_capsules=100)
    physical = game.ship.physical_transit
    game.ship.physical_transit = replace(physical, second_repair_evidence=None)
    game = save_and_load(game)
    before = pickle.dumps(game)
    with pytest.raises(RuntimeError, match="authorization and repair"):
        engine.prepare_inertial_recovery(game)
    assert pickle.dumps(game) == before


def test_cancel_then_reauthorize_keeps_current_repair_and_monotonic_ids():
    game = repaired_second("coast")
    engine = Engine()
    evidence = game.ship.physical_transit.second_repair_evidence
    fuel = game.ship.antimatter_capsules
    first = engine.authorize_manual_inertial_recovery(game, max_capsules=100)
    engine.cancel_manual_inertial_recovery(game)
    assert game.ship.physical_transit.second_repair_evidence == evidence
    second = engine.authorize_manual_inertial_recovery(game, max_capsules=100)
    assert second.attempt_id > first.attempt_id
    assert second.paid_predecessor_id == first.paid_predecessor_id
    assert game.ship.antimatter_capsules == fuel
    engine.prepare_inertial_recovery(game)
    assert game.ship.physical_transit.recovery_lineage.spent_through_authorization_id == second.attempt_id
