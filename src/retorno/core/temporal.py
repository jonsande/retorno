"""Intervals for ship proper time and nominal biological ageing."""
from __future__ import annotations

import math

from retorno.config.balance import Balance


SPEED_OF_LIGHT_KM_S = 299_792.458


def proper_time_interval(dt_galactic: float, beta: float) -> float:
    """Return seconds of proper time for constant speed, with 0 <= beta < 1."""
    if not math.isfinite(dt_galactic) or dt_galactic < 0:
        raise ValueError("Galactic interval must be finite and nonnegative")
    if not math.isfinite(beta) or not 0 <= beta < 1:
        raise ValueError("Speed must be finite and satisfy 0 <= beta < 1")
    return dt_galactic * math.sqrt(1.0 - beta * beta)


def biological_time_interval(dt_ship: float, is_hibernating: bool) -> float:
    """Return nominal ageing; life-support effectiveness is a later model."""
    rate = Balance.HIBERNATION_BIO_AGE_RATE_NOMINAL if is_hibernating else 1.0
    if not math.isfinite(rate) or rate < 0:
        raise ValueError("Biological ageing rate must be finite and nonnegative")
    return dt_ship * rate
