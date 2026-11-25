"""Historical fixed-speed fixture for subsystem regressions predating D2A.

Public interstellar actions use physical navigation. These older tests still
exercise the ordinary interval integrator's electrical and speed accounting.
"""
from retorno.config.balance import Balance
from retorno.core.actions import Travel
from retorno.core.engine import Engine
from retorno.model.events import EventType, Severity, SourceRef
from retorno.model.systems import SystemState


class LegacyTransitEngine(Engine):
    def estimate_travel_duration(self, state, destination_id):
        distance = self._known_hop_distance(state, destination_id)
        if distance is None:
            return None
        if self._is_local_hop(state, state.world.current_node_id, destination_id, distance):
            return super().estimate_travel_duration(state, destination_id)
        speed = state.ship.effective_cruise_speed()
        return distance / speed * Balance.YEAR_S if speed > 0 else None

    def apply_action(self, state, action):
        if not isinstance(action, Travel):
            return super().apply_action(state, action)
        destination = action.node_id
        distance = self._known_hop_distance(state, destination)
        if (distance is None or self._is_local_hop(state, state.world.current_node_id,
                                                   destination, distance)
                or state.ship.operational_in_transit or state.ship.docked_node_id):
            return super().apply_action(state, action)
        speed = state.ship.effective_cruise_speed()
        if speed <= 0 or state.ship.engine_operating_state() in {SystemState.OFFLINE, SystemState.CRITICAL}:
            return super().apply_action(state, action)
        cost = self.engine_fuel_cost(state, distance, speed)
        if state.ship.antimatter_capsules < cost:
            return super().apply_action(state, action)
        ship = state.ship
        ship.antimatter_capsules -= cost
        ship.in_transit = True
        ship.transit_from = state.world.current_node_id
        ship.transit_to = destination
        ship.transit_start_t = state.clock.t
        duration = distance / speed * Balance.YEAR_S
        ship.arrival_t = state.clock.t + duration
        ship.transit_speed_ly_per_year = speed
        ship.last_travel_distance_ly = distance
        ship.last_travel_is_local = False
        ship.transit_prev_op_mode = ship.op_mode
        ship.transit_prev_op_mode_source = ship.op_mode_source
        if not action.no_cruise:
            ship.op_mode = "CRUISE"
            ship.op_mode_source = "auto"
            for key in ("sensors", "data_core", "drone_bay"):
                system = ship.systems.get(key)
                if system is not None:
                    system.forced_offline = True
                    system.state = SystemState.OFFLINE
                    if system.service:
                        system.service.is_running = False
        event = self._make_event(
            state, EventType.TRAVEL_STARTED, Severity.INFO,
            SourceRef(kind="ship", id=ship.ship_id),
            f"Historical fixture transit to {destination}",
            data={"from": ship.transit_from, "to": destination, "distance_ly": distance,
                  "eta_years": duration / Balance.YEAR_S, "eta_s": duration,
                  "arrival_t": ship.arrival_t, "speed_ly_per_year": speed,
                  "fuel_cost": cost, "fuel_remaining": ship.antimatter_capsules,
                  "local": False},
        )
        self._record_event(state.events, event)
        return [event]
