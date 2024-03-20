from functools import wraps
from sst_funcs.globalVars import (GLOBAL_ACTIVE_DETECTORS,
                                  GLOBAL_PLOT_DETECTORS, GLOBAL_SELECTED)
from sst_funcs.detectors import (activate_detector,
                                 deactivate_detector, plot_detector_set)
from .plan_stubs import set_exposure


def _sst_setup_detectors(func):
    @wraps(func)
    def _inner(*args, extra_dets=[], dwell=None, **kwargs):
        # Should check for redundancy
        for det in extra_dets:
            activate_detector(det)

        yield from set_exposure(dwell)

        ret = yield from func(GLOBAL_ACTIVE_DETECTORS, *args, **kwargs)

        for det in extra_dets:
            deactivate_detector(det)

        return ret
    return _inner


def _sst_add_plot_md(func):
    @wraps(func)
    def _inner(*args, md=None, plot_detectors=None, **kwargs):
        md = md or {}
        plot_hints = {}
        if plot_detectors is not None:
            plot_detector_set(plot_detectors)
        for role, detlist in GLOBAL_PLOT_DETECTORS.items():
            plot_hints[role] = []
            for det in detlist:
                if det in GLOBAL_ACTIVE_DETECTORS:
                    if hasattr(det, "get_plot_hints"):
                        plot_hints[role] += det.get_plot_hints()
                    else:
                        plot_hints[role].append(det.name)
        _md = {'plot_hints': plot_hints}
        _md.update(md)
        return (yield from func(*args, md=_md, **kwargs))
    return _inner


def _sst_add_sample_md(func):
    @wraps(func)
    def _inner(*args, md=None, **kwargs):
        md = md or {}
        _md = {"sample_name": GLOBAL_SELECTED.get("name", ""),
               "sample_id": GLOBAL_SELECTED.get("sample_id", ""),
               "sample_desc": GLOBAL_SELECTED.get("description", ""),
               "sample_set": GLOBAL_SELECTED.get("group", "")}
        _md.update(md)
        return (yield from func(*args, md=_md, **kwargs))
    return _inner


def _sst_add_comment(func):
    @wraps(func)
    def _inner(*args, md=None, comment=None, **kwargs):
        md = md or {}
        if comment is not None:
            _md = {"comment": comment}
        else:
            _md = {}
        _md.update(md)
        return (yield from func(*args, md=_md, **kwargs))
    return _inner


def sst_base_scan_decorator(func):
    @wraps(func)
    @_sst_setup_detectors
    @_sst_add_sample_md
    @_sst_add_plot_md
    @_sst_add_comment
    def _inner(*args, **kwargs):
        return (yield from func(*args, **kwargs))
    return _inner


def sst_builtin_scan_wrapper(func):
    """
    Designed to wrap bluesky built-in scans to produce an sst version
    """
    base_name = func.__name__
    plan_name = f"sst_{base_name}"
    _inner = sst_base_scan_decorator(func)

    d = f"""Modifies {base_name} to automatically fill
dets with global active beamline detectors.
Other detectors may be added on the fly via extra_dets
---------------------------------------------------------
"""

    _inner.__doc__ = d + func.__doc__
    _inner.__name__ = plan_name
    return _inner
