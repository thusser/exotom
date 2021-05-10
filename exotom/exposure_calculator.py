from typing import Callable

from local_settings import EXPOSURE_TIME_MODEL_BY_INSTRUMENT


def calculate_exposure_time(mag: float, instrument_type: str) -> float:
    """Calculates exposure time in seconds for star of given magnitude."""

    exposure_time_model: Callable = EXPOSURE_TIME_MODEL_BY_INSTRUMENT[instrument_type]
    return exposure_time_model(mag)
