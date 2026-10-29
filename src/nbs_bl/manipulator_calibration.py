"""
Saved manipulator calibration.

MANIPULATOR_CONFIG (Redis) holds:

- ``rotation_center``: [x, y], the motor position at which the rotation axis
  is in the beam (older profiles saved ``origin`` as [x, y, z, r]).
- ``holder``: {"type", "sides"} of the bar the side points belong to.
- ``calibration``: {side number: [p1, p2, p3]}, as ``update_side`` takes.
- ``rigid_fit``: the last rigid-bar fit, for reference.
"""

import warnings

import numpy as np

from nbs_bl.queueserver import GLOBAL_USER_STATUS

_CONFIG = None


def manipulator_config():
    """The MANIPULATOR_CONFIG status dict, created on first use."""
    global _CONFIG
    if _CONFIG is None:
        _CONFIG = GLOBAL_USER_STATUS.request_status_dict(
            "MANIPULATOR_CONFIG", use_redis=True
        )
    return _CONFIG


def holder_signature(holder):
    return {"type": type(holder).__name__, "sides": int(holder.sides)}


def save_rotation_center(manipulator, config=None):
    config = manipulator_config() if config is None else config
    config["rotation_center"] = [float(v) for v in manipulator.rotation_center[:2]]


def save_side(manipulator, side, points, config=None):
    """Save a side's (numbered from 1) calibration points."""
    config = manipulator_config() if config is None else config
    signature = holder_signature(manipulator.holder)
    calibration = dict(config.get("calibration", {}))
    if not _calibration_matches(manipulator.holder, config):
        calibration = {}
    calibration[f"{side}"] = [[float(v) for v in p] for p in points]
    config["holder"] = signature
    config["calibration"] = calibration


def clear_sides(config=None):
    config = manipulator_config() if config is None else config
    config["calibration"] = {}


def _saved_center(config):
    if "rotation_center" in config:
        return config["rotation_center"]
    if "origin" in config:
        return list(config["origin"])[:2]
    return None


def _calibration_matches(holder, config):
    saved = config.get("holder")
    if saved is None:
        # Saved before the holder was recorded: only 4-sided bars were calibrated
        return type(holder).__name__ == "Standard4SidedBar"
    return saved == holder_signature(holder)


def restore_manipulator_calibration(manipulator, config=None):
    """
    Apply the saved rotation center and side calibration to a manipulator.

    Side points are applied only if they were saved for the same holder type
    and number of sides.

    Returns
    -------
    bool
        True if side points were applied.
    """
    config = manipulator_config() if config is None else config
    center = _saved_center(config)
    if center is not None and hasattr(manipulator, "set_rotation_center"):
        manipulator.set_rotation_center(*center)
    holder = getattr(manipulator, "holder", None)
    calibration = config.get("calibration", {})
    if not calibration or not hasattr(holder, "update_side"):
        return False
    if not _calibration_matches(holder, config):
        warnings.warn(
            f"Saved manipulator calibration is for {config.get('holder')}, not "
            f"{holder_signature(holder)}; not applying it. Recalibrate the bar."
        )
        return False
    for side, points in calibration.items():
        side = int(side)
        if 1 <= side <= holder.sides:
            holder.update_side(side - 1, *(np.asarray(p, dtype=float) for p in points))
    return True
