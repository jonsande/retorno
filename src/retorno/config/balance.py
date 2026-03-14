from __future__ import annotations


class Balance:
    DEFAULT_RNG_SEED = 36892
    DAY_S = 86400.0
    YEAR_S = 365.0 * DAY_S
    # Legacy operational region model (kept for diagnostics/backward checks).
    GALAXY_OP_REGION_CENTER_X_LY = 0.0
    GALAXY_OP_REGION_CENTER_Y_LY = 0.0
    GALAXY_OP_REGION_CENTER_Z_LY = 0.0
    GALAXY_OP_BULGE_RADIUS_LY = 5.0
    GALAXY_OP_DISK_OUTER_RADIUS_LY = 15.0
    # Physical galaxy model (effective galactic semantics).
    GALAXY_PHYSICAL_CENTER_X_LY = 0.0
    GALAXY_PHYSICAL_CENTER_Y_LY = 0.0
    GALAXY_PHYSICAL_CENTER_Z_LY = 0.0
    GALAXY_PHYSICAL_RADIUS_LY = 500000.0
    GALAXY_PHYSICAL_BULGE_RADIUS_LY = 10000.0
    GALAXY_PHYSICAL_DISK_OUTER_RADIUS_LY = 400000.0
    GALAXY_OP_TO_PHYSICAL_SCALE = 1.0
    GALAXY_OP_ORIGIN_PHYSICAL_X_LY = 250000.0
    GALAXY_OP_ORIGIN_PHYSICAL_Y_LY = 0.0
    GALAXY_OP_ORIGIN_PHYSICAL_Z_LY = 0.0
    HIBERNATE_CHUNK_S = 7 * DAY_S
    HIBERNATE_WAKE_CHECK_S = 1 * 60 * 60
    HIBERNATE_WAKE_EVENT_TYPES = {"drone_low_battery"}
    # Startup sequence (new game only)
    STARTUP_SEQUENCE_ENABLED = True
    STARTUP_SEQUENCE_LINE_DELAY_S = 1.7
    STARTUP_SEQUENCE_TYPEWRITER = False
    STARTUP_SEQUENCE_TYPEWRITER_CPS = 195
    STARTUP_SEQUENCE_SKIPPABLE = True

    # Power/alerts
    BUS_INSTABILITY_AFTER_S = 120
    LOW_POWER_QUALITY_THRESHOLD = 0.7
    R_REF = 0.05
    HULL_RAD_REF = 0.003
    BROWNOUT_SUSTAINED_AFTER_S = 30
    BROWNOUT_DEGRADE_MULT_DISTRIBUTION = 3.0
    BROWNOUT_DEGRADE_MULT_POWER_CORE = 2.0
    LIFE_SUPPORT_CRITICAL_GRACE_S = 300
    POWER_QUALITY_BLOCK_THRESHOLD = 0.55
    POWER_QUALITY_CRITICAL_THRESHOLD = 0.40
    POWER_QUALITY_COLLAPSE_THRESHOLD = 0.25
    POWER_QUALITY_SHED_INTERVAL_S = 10.0

    # Job times (seconds)
    # Base repair duration for ship systems.
    REPAIR_TIME_S = 45.0
    # Drone deployment time.
    DEPLOY_TIME_S = 13.0
    # Drone reboot time.
    REBOOT_TIME_S = 25.0
    # Drone recall time.
    RECALL_TIME_S = 25.0
    # Docking time to a node.
    DOCK_TIME_S = 60.0
    # Undocking time from a node.
    UNDOCK_TIME_S = 45.0
    # Module installation time.
    INSTALL_TIME_S = 30.0
    # Ship module uninstallation time.
    UNINSTALL_TIME_S = 25.0
    # Drone module installation/uninstallation (bay operation) times.
    DRONE_INSTALL_TIME_S = 35.0
    DRONE_UNINSTALL_TIME_S = 25.0
    # Salvage scrap time model: base + per unit.
    SALVAGE_SCRAP_BASE_S = 5.0
    SALVAGE_SCRAP_PER_UNIT_S = 1.5
    # Drone salvage scrap time for one full cargo-load cycle.
    DRONE_SALVAGE_SCRAP_BASE_LOAD_TIME_S = 35.0
    # Salvage module job time.
    SALVAGE_MODULE_TIME_S = 25.0
    # Salvage data job time.
    SALVAGE_DATA_TIME_S = 40.0
    # Drone survey job time.
    DRONE_SURVEY_TIME_S = 20.0
    # Recoverable drone salvage time model: base + per unit.
    DRONE_SALVAGE_DRONE_BASE_TIME_S = 35.0
    DRONE_SALVAGE_DRONE_PER_UNIT_S = 4.0
    # Self-test repair job time and amount.
    SELFTEST_REPAIR_TIME_S = 18.0
    SELFTEST_REPAIR_AMOUNT = 0.05
    # Scrap cost per unit of health repaired.
    REPAIR_SCRAP_PER_HEALTH = 20 # ???
    SELFTEST_REPAIR_SCRAP_PER_HEALTH = 12 # ???
    # Active repair jobs can fail with a low base chance.
    REPAIR_JOB_FAIL_P_BASE = 0.10
    # On repair failure, keep only this fraction of the originally paid scrap.
    REPAIR_JOB_FAIL_SCRAP_CONSUME_FRACTION = 0.25
    # Cargo audit time.
    CARGO_AUDIT_TIME_S = 11.0
    # Auth recover (MED) time and power draw.
    AUTH_RECOVER_MED_TIME_S = 245.0
    AUTH_RECOVER_MED_POWER_KW = 0.8
    # Auth recover (ENG) time and power draw.
    AUTH_RECOVER_ENG_TIME_S = 365.0
    AUTH_RECOVER_ENG_POWER_KW = 1.0
    # Auth recover (OPS) time and power draw.
    AUTH_RECOVER_OPS_TIME_S = 780.0
    AUTH_RECOVER_OPS_POWER_KW = 1.2
    # Auth recover (SEC) time and power draw.
    AUTH_RECOVER_SEC_TIME_S = 1095.0
    AUTH_RECOVER_SEC_POWER_KW = 1.4

    # Transit wear / warnings
    # Multiplier applied to wear during normal transit.
    TRANSIT_WEAR_MULT_NORMAL = 2.5
    # Minimum travel years before warning about transit wear.
    TRANSIT_WARN_YEARS = 0.2
    # Hull wear multipliers.
    HULL_BASE_DECAY_PER_S = 1.0e-11
    HULL_TRANSIT_DECAY_MULT = 1.5
    HULL_RAD_DECAY_MULT_MAX = 3.0
    HULL_INTERNAL_RAD_MIN_INGRESS = 0.10
    HULL_INTERNAL_RAD_MAX_INGRESS = 1.00

    # Emergency deploy risk (per second)
    # Probability per second that an emergency deploy fails or glitches.
    EMERGENCY_DEPLOY_P_FAIL_PER_S = 0.03
    EMERGENCY_DEPLOY_P_GLITCH_PER_S = 0.05

    # Drone recall/reboot success probability clamps
    # Min/max success probabilities for recall/reboot, plus integrity gates.
    DRONE_REBOOT_P_MIN = 0.2
    DRONE_REBOOT_P_MAX = 0.9
    DRONE_RECALL_P_MIN = 0.3
    DRONE_RECALL_P_MAX = 0.95
    DRONE_RECALL_MIN_INTEGRITY = 0.10
    DRONE_DEPLOY_MIN_INTEGRITY = 0.10
    DRONE_MOVE_MIN_INTEGRITY = 0.10

    # Salvage probabilities
    SALVAGE_SCRAP_FIND_MODULE_P = 0.10
    SALVAGE_MODULE_FIND_P = 0.75
    SALVAGE_DATA_LOG_P_STATION_SHIP = 0.70
    SALVAGE_DATA_LOG_P_OTHER = 0.50
    SALVAGE_DATA_MAIL_P_STATION_SHIP = 0.50
    SALVAGE_DATA_MAIL_P_OTHER = 0.30
    SALVAGE_DATA_FRAG_P_STATION_DERELICT = 0.25
    SALVAGE_DATA_FRAG_P_OTHER = 0.15
    # Survey false-negative probability when recoverable data files really exist.
    # Positive surveys should read as "possible signatures" (not certainty), and this
    # knob allows future drone modules to improve survey efficacy by reducing misses.
    DRONE_SURVEY_DATA_FALSE_NEGATIVE_P = 0.35
    # Recoverable drones by node kind (procedural + authored fallback).
    SALVAGE_DRONES_BY_KIND = {
        "station": {"prob": 0.02, "min": 1, "max": 2},
        "ship": {"prob": 0.08, "min": 1, "max": 3},
        "derelict": {"prob": 0.06, "min": 1, "max": 2},
        "relay": {"prob": 0.00, "min": 0, "max": 0},
        "waystation": {"prob": 0.01, "min": 1, "max": 1},
        "origin": {"prob": 0.00, "min": 0, "max": 0},
        "transit": {"prob": 0.00, "min": 0, "max": 0},
    }
    # Initial stats for salvaged drones.
    SALVAGED_DRONE_INTEGRITY_MIN = 0.45
    SALVAGED_DRONE_INTEGRITY_MAX = 0.85
    SALVAGED_DRONE_BATTERY_MIN = 0.20
    SALVAGED_DRONE_BATTERY_MAX = 0.80
    SALVAGED_DRONE_DOSE_MIN = 0.0
    SALVAGED_DRONE_DOSE_MAX = 0.8

    # System health thresholds
    SYSTEM_HEALTH_OFFLINE = 0.0
    SYSTEM_HEALTH_CRITICAL = 0.35
    SYSTEM_HEALTH_DAMAGED = 0.60
    SYSTEM_HEALTH_LIMITED = 0.85
    SYSTEM_HEALTH_MIN_ON = 0.0

    # Power core output multipliers by state
    POWER_CORE_MULT_OFFLINE = 0.0
    POWER_CORE_MULT_CRITICAL = 0.25
    POWER_CORE_MULT_DAMAGED = 0.50
    POWER_CORE_MULT_LIMITED = 0.75
    POWER_CORE_MULT_NOMINAL = 1.0

    # Sensors
    SENSORS_RANGE_LY = 2.5
    SENSORS_DETECT_P_NEAR = 0.95
    SENSORS_DETECT_P_FAR = 0.30
    SENSORS_DETECT_P_NOMINAL = 1.00
    SENSORS_DETECT_P_LIMITED = 0.85
    SENSORS_DETECT_P_DAMAGED = 0.60
    SENSORS_DETECT_P_CRITICAL = 0.35

    # Route solving
    ROUTE_SOLVE_MIN_S = 100.0
    ROUTE_SOLVE_MAX_S = 6800.0
    # Hard cap for any single travel hop or operational link publication.
    MAX_ROUTE_HOP_LY = 45.0
    UPLINK_FAILSAFE_N = 2
    # If no new routes to unvisited nodes exist within this distance from the current node,
    # the mobility failsafe may trigger (after N uplinks with no new routes).
    MOBILITY_FAILSAFE_MAX_DIST_LY = 20.0
    # Corrupt intel handling: chance to fail vs spawn a procedural hub contact.
    INTEL_CORRUPT_P_FAIL = 0.50
    # Max radius (ly) when spawning a procedural hub from corrupt intel.
    INTEL_CORRUPT_SPAWN_RADIUS_LY = 40.0
    # Dead-node failsafe toggle.
    DEADNODE_FAILSAFE_ENABLED = True
    # Stuck thresholds (randomized per node within these ranges).
    DEADNODE_STUCK_UPLINKS_MIN = 10
    DEADNODE_STUCK_UPLINKS_MAX = 15
    DEADNODE_STUCK_YEARS_MIN = 25.0
    DEADNODE_STUCK_YEARS_MAX = 35.0
    # Dead thresholds (randomized per node within these ranges).
    DEADNODE_DEAD_UPLINKS_MIN = 20
    DEADNODE_DEAD_UPLINKS_MAX = 30
    DEADNODE_DEAD_YEARS_MIN = 50.0
    DEADNODE_DEAD_YEARS_MAX = 100.0
    # Cooldown between failsafe actions (years).
    DEADNODE_ACTION_COOLDOWN_YEARS = 5.0
    # Max indirect attempts before falling back to direct strategy.
    DEADNODE_MAX_INDIRECT_ATTEMPTS = 2

    # Legacy fallback for non-forced lore injection probability.
    # The scheduler now uses LORE_NON_FORCED_INJECT_P as the primary knob; this value is
    # only used as fallback when that knob is missing.
    LORE_SINGLES_BASE_P = 0.05
    # Enables/disables periodic lore scheduler evaluations in engine.tick.
    # Keep enabled for the node-pool model where non-forced lore is injected by cycle.
    LORE_SCHEDULER_ENABLED = True
    # Period (in in-game years) between non-forced lore injection evaluations.
    # Lower values mean more frequent checks; 1.0 means "once per in-game year".
    LORE_NON_FORCED_INTERVAL_YEARS = 1.0
    # Probability applied at each non-forced scheduler cycle for every eligible piece.
    # This controls how often optional lore gets assigned to candidate node pools.
    LORE_NON_FORCED_INJECT_P = 0.05
    # Toggle deterministic lore/intel behavior across processes for equal seed/state/action sequence.
    # False restores legacy process-dependent behavior for lore seed derivation and set iteration order.
    DETERMINISTIC_LORE_INTEL = True
    
    # Local (low scale) movement
    # Travel speed for local (km/mi) hops inside the same sector.
    LOCAL_TRAVEL_SPEED_KM_S = 20.0
    # Max ly distance to consider a contact "local travel".
    LOCAL_TRAVEL_RADIUS_LY = 0.01
    # Randomized fine distance bounds for local travel (km).
    LOCAL_TRAVEL_MIN_KM = 200.0
    LOCAL_TRAVEL_MAX_KM = 50000.0
    # Starting scrap in the ship inventory.
    STARTING_SCRAP = 64

    # Drone battery/integrity maintenance
    # Per-task battery drains (fractions).
    DRONE_BATTERY_DRAIN_DEPLOY = 0.06
    DRONE_BATTERY_DRAIN_RECALL = 0.05
    DRONE_BATTERY_DRAIN_REPAIR = 0.08
    DRONE_BATTERY_DRAIN_SALVAGE = 0.07
    DRONE_BATTERY_DRAIN_REBOOT = 0.04
    DRONE_BATTERY_DRAIN_SELFTEST = 0.02
    DRONE_BATTERY_DRAIN_MOVE = 0.05
    # Charge rate per second when in bay (fractions).
    DRONE_BATTERY_CHARGE_PER_S = 0.005 # original 0.02
    DRONE_BAY_LIMITED_CHARGE_RATE_MULT = 0.5
    DRONE_BAY_DAMAGED_CHARGE_RATE_MULT = 0.25
    # Charge speed multiplier when ship SoC is low.
    DRONE_BATTERY_CHARGE_LOW_MULT = 0.25
    DRONE_BAY_LIMITED_ETA_MULT = 1.5
    DRONE_BAY_DAMAGED_ETA_MULT = 2.0
    DRONE_BAY_DAMAGED_INTEGRITY_RISK_P = 0.10
    DRONE_BAY_DAMAGED_INTEGRITY_HIT = 0.10
    DRONE_BAY_LIMITED_REPAIR_RATE_MULT = 0.5
    DRONE_BAY_DAMAGED_REPAIR_RATE_MULT = 0.5
    DRONE_BAY_CRITICAL_REPAIR_RATE_MULT = 0.25
    DRONE_BAY_DAMAGED_REPAIR_SCRAP_MULT = 2.0
    DRONE_BAY_CRITICAL_REPAIR_SCRAP_MULT = 2.0
    DRONE_BAY_CRITICAL_REPAIR_FAIL_P = 0.10
    DRONE_BAY_CRITICAL_REPAIR_FAIL_HIT = 0.01
    # Power draw for charging a drone (kW).
    DRONE_CHARGE_KW = 0.2
    # Minimum net power required to allow drone charging.
    DRONE_CHARGE_NET_MIN_KW = -0.2
    DRONE_BATTERY_IDLE_DRAIN_DEPLOYED_PER_S = 0.00002 # Velocidad a la que descarga sin hacer nada
    DRONE_CARGO_CAPACITY_BASE = 10.0
    DRONE_BASE_DECAY_PER_S = 1.0e-7
    DRONE_DECON_RAD_PER_S = 0.01
    DRONE_RAD_DOSE_WARN = 1.0
    DRONE_RAD_DOSE_HIGH = 3.0
    DRONE_RAD_DOSE_CRITICAL = 6.0
    DRONE_RAD_DECAY_MULT_WARN = 1.2
    DRONE_RAD_DECAY_MULT_HIGH = 1.8
    DRONE_RAD_DECAY_MULT_CRITICAL = 3.0
    # Procedural node ambient radiation (rad/s).
    # Authored locations keep their explicit radiation values.
    PROCEDURAL_RAD_BASE = 0.00082
    PROCEDURAL_RAD_MIN = 0.0001
    PROCEDURAL_RAD_REGION_MULT = {
        "bulge": 2.2,
        "disk": 1.0,
        "halo": 0.55,
    }
    PROCEDURAL_RAD_KIND_MULT = {
        "ship": 1.8,  # WRECK_* ids are generated as kind="ship".
    }
    PROCEDURAL_RAD_VARIATION_MIN = 0.50
    PROCEDURAL_RAD_VARIATION_MAX = 1.70
    PROCEDURAL_RAD_SPIKE_CHANCE = 0.16
    PROCEDURAL_RAD_SPIKE_MULT_MIN = 2.80
    PROCEDURAL_RAD_SPIKE_MULT_MAX = 11.50
    # Radiation level thresholds (4-band): low / elevated / high / extreme.
    # Values are ">= threshold"; below elevated is considered low.
    RAD_LEVEL_ENV_ELEVATED = 0.001
    RAD_LEVEL_ENV_HIGH = 0.003
    RAD_LEVEL_ENV_EXTREME = 0.020
    RAD_LEVEL_INTERNAL_ELEVATED = 0.0003
    RAD_LEVEL_INTERNAL_HIGH = 0.0010
    RAD_LEVEL_INTERNAL_EXTREME = 0.0050
    RAD_LEVEL_DRONE_DOSE_ELEVATED = DRONE_RAD_DOSE_WARN
    RAD_LEVEL_DRONE_DOSE_HIGH = DRONE_RAD_DOSE_HIGH
    RAD_LEVEL_DRONE_DOSE_EXTREME = DRONE_RAD_DOSE_CRITICAL
    # Hibernate wake guardrail for ambient radiation while in transit.
    HIBERNATE_WAKE_ON_ENV_RAD_THRESHOLD = True
    HIBERNATE_WAKE_ENV_RAD_THRESHOLD_RAD_PER_S = RAD_LEVEL_ENV_HIGH
    # Repair efficiency per scrap spent.
    DRONE_REPAIR_INTEGRITY_PER_SCRAP = 5.0
    # Thresholds for alerts and action gating.
    DRONE_LOW_BATTERY_THRESHOLD = 0.15
    DRONE_MIN_BATTERY_FOR_TASK = 0.10
    DRONE_MIN_BATTERY_FOR_RECALL = 0.05

    # Bootstrap node salvage (ECHO_7)
    # ECHO_7_SCRAP_MIN = 50
    # ECHO_7_SCRAP_MAX = 70
    # ECHO_7_MODULES_MIN = 0
    # ECHO_7_MODULES_MAX = 2
