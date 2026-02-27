from __future__ import annotations


class Balance:
    DEFAULT_RNG_SEED = 36892
    DAY_S = 86400.0
    YEAR_S = 365.0 * DAY_S
    HIBERNATE_CHUNK_S = 7 * DAY_S
    HIBERNATE_WAKE_CHECK_S = 1 * 60 * 60
    HIBERNATE_WAKE_EVENT_TYPES = {"drone_low_battery"}
    # Startup sequence (new game only)
    STARTUP_SEQUENCE_ENABLED = True
    STARTUP_SEQUENCE_LINE_DELAY_S = 2.0
    STARTUP_SEQUENCE_TYPEWRITER = False
    STARTUP_SEQUENCE_TYPEWRITER_CPS = 195
    STARTUP_SEQUENCE_SKIPPABLE = True

    # Power/alerts
    BUS_INSTABILITY_AFTER_S = 120
    LOW_POWER_QUALITY_THRESHOLD = 0.7
    R_REF = 0.05

    # Job times (seconds)
    # Base repair duration for ship systems.
    REPAIR_TIME_S = 25.0
    # Drone deployment time.
    DEPLOY_TIME_S = 13.0
    # Drone reboot time.
    REBOOT_TIME_S = 15.0
    # Drone recall time.
    RECALL_TIME_S = 10.0
    # Docking time to a node.
    DOCK_TIME_S = 12.0
    # Module installation time.
    INSTALL_TIME_S = 30.0
    # Salvage scrap time model: base + per unit.
    SALVAGE_SCRAP_BASE_S = 4.0
    SALVAGE_SCRAP_PER_UNIT_S = 1.5
    # Salvage module job time.
    SALVAGE_MODULE_TIME_S = 12.0
    # Salvage data job time.
    SALVAGE_DATA_TIME_S = 18.0
    # Self-test repair job time and amount.
    SELFTEST_REPAIR_TIME_S = 18.0
    SELFTEST_REPAIR_AMOUNT = 0.05
    # Scrap cost per unit of health repaired.
    REPAIR_SCRAP_PER_HEALTH = 20
    SELFTEST_REPAIR_SCRAP_PER_HEALTH = 12
    # Cargo audit time.
    CARGO_AUDIT_TIME_S = 11.0

    # Transit wear / warnings
    # Multiplier applied to wear during normal transit.
    TRANSIT_WEAR_MULT_NORMAL = 2.5
    # Minimum travel years before warning about transit wear.
    TRANSIT_WARN_YEARS = 0.2

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

    # Lore singles: base probability per eligible trigger that a single will be attempted.
    # This is checked before weights are applied. Higher values = more frequent singles
    # across uplink/dock/salvage_data triggers. Weights only affect which single is chosen.
    LORE_SINGLES_BASE_P = 0.05
    
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
    DRONE_BATTERY_CHARGE_PER_S = 0.02
    # Charge speed multiplier when ship SoC is low.
    DRONE_BATTERY_CHARGE_LOW_MULT = 0.25
    # Power draw for charging a drone (kW).
    DRONE_CHARGE_KW = 0.2
    # Minimum net power required to allow drone charging.
    DRONE_CHARGE_NET_MIN_KW = -0.2
    DRONE_BATTERY_IDLE_DRAIN_DEPLOYED_PER_S = 0.00002 # Velocidad a la que descarga sin hacer nada
    # Repair efficiency per scrap spent.
    DRONE_REPAIR_INTEGRITY_PER_SCRAP = 0.02
    # Thresholds for alerts and action gating.
    DRONE_LOW_BATTERY_THRESHOLD = 0.15
    DRONE_MIN_BATTERY_FOR_TASK = 0.10
    DRONE_MIN_BATTERY_FOR_RECALL = 0.05

    # Bootstrap node salvage (ECHO_7)
    # ECHO_7_SCRAP_MIN = 50
    # ECHO_7_SCRAP_MAX = 70
    # ECHO_7_MODULES_MIN = 0
    # ECHO_7_MODULES_MAX = 2
