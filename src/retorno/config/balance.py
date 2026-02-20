from __future__ import annotations


class Balance:
    # Power/alerts
    BUS_INSTABILITY_AFTER_S = 120
    LOW_POWER_QUALITY_THRESHOLD = 0.7
    R_REF = 0.05

    # Job times (seconds)
    REPAIR_TIME_S = 25.0
    DEPLOY_TIME_S = 6.0
    REBOOT_TIME_S = 15.0
    RECALL_TIME_S = 10.0
    DOCK_TIME_S = 12.0
    INSTALL_TIME_S = 10.0
    SALVAGE_SCRAP_BASE_S = 4.0
    SALVAGE_SCRAP_PER_UNIT_S = 1.5
    SALVAGE_MODULE_TIME_S = 12.0

    # Emergency deploy risk (per second)
    EMERGENCY_DEPLOY_P_FAIL_PER_S = 0.03
    EMERGENCY_DEPLOY_P_GLITCH_PER_S = 0.05

    # Drone recall/reboot success probability clamps
    DRONE_REBOOT_P_MIN = 0.2
    DRONE_REBOOT_P_MAX = 0.9
    DRONE_RECALL_P_MIN = 0.3
    DRONE_RECALL_P_MAX = 0.95

    # Salvage probabilities
    SALVAGE_SCRAP_FIND_MODULE_P = 0.10
    SALVAGE_MODULE_FIND_P = 0.75

    # Bootstrap node salvage (ECHO_7)
    ECHO_7_SCRAP_MIN = 50
    ECHO_7_SCRAP_MAX = 70
    ECHO_7_MODULES_MIN = 0
    ECHO_7_MODULES_MAX = 2
