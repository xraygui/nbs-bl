from functools import wraps
from sst_funcs.globalVars import (
    GLOBAL_ACTIVE_DETECTORS,
    GLOBAL_PLOT_DETECTORS,
    GLOBAL_SELECTED,
    GLOBAL_ENERGY,
)
from sst_funcs.detectors import (
    activate_detector,
    deactivate_detector,
    activate_detector_set,
)
from sst_funcs.utils import merge_func
from .plan_stubs import set_exposure
from bluesky.plan_stubs import mv
from .preprocessors import wrap_metadata
from sst_funcs.plans.groups import repeat
from sst_funcs.settings import settings

def _beamline_setup(func):
    @merge_func(func)
    def inner(*args, sample=None, eslit=None, energy=None, **kwargs):
        """
        Parameters
        ----------
        sample : int or str, optional
            The sample id. If not None, the sample is moved into the beam at a 45 degree angle.
        eslit : float, optional
            If not None, will change the beamline exit slit. Note that currently, eslit values are given as -2* the desired exit slit size in mm.
        """

        #if sample is not None:
        #    yield from sample_move(0, 0, 45, sample)
        if eslit is not None:
            yield from mv(GLOBAL_ENERGY['slit'], eslit)
        if energy is not None:
            yield from mv(GLOBAL_ENERGY['energy'], energy)
        return (yield from func(*args, **kwargs))

    return inner

def _wrap_xas(element):
    def decorator(func):
        return wrap_metadata({"edge": element, "scantype": "xas"})(func)
    return decorator


def _sst_setup_detectors(func):
    @merge_func(func, ["detectors"])
    def _inner(*args, extra_dets=[], dwell=None, **kwargs):
        """
        Parameters
        ----------
        extra_dets : list, optional
            A list of extra detectors to be activated for the scan, by default [].
        dwell : float, optional
            The exposure time in seconds for all detectors, by default None.
        """
        for det in extra_dets:
            activate_detector(det)

        yield from set_exposure(dwell)

        ret = yield from func(GLOBAL_ACTIVE_DETECTORS, *args, **kwargs)

        for det in extra_dets:
            deactivate_detector(det)

        return ret

    return _inner


def _sst_add_plot_md(func):
    @merge_func(func)
    def _inner(*args, md=None, plot_detectors=None, **kwargs):
        md = md or {}
        plot_hints = {}
        if plot_detectors is not None:
            activate_detector_set(plot_detectors)
        for role, detlist in GLOBAL_PLOT_DETECTORS.items():
            plot_hints[role] = []
            for det in detlist:
                if det in GLOBAL_ACTIVE_DETECTORS:
                    if hasattr(det, "get_plot_hints"):
                        plot_hints[role] += det.get_plot_hints()
                    else:
                        plot_hints[role].append(det.name)
        _md = {"plot_hints": plot_hints}
        _md.update(md)
        return (yield from func(*args, md=_md, **kwargs))

    return _inner


def _sst_add_sample_md(func):
    @merge_func(func)
    def _inner(*args, md=None, **kwargs):
        """
        Sample information is automatically added to the run md
        """
        md = md or {}
        _md = {
            "sample_name": GLOBAL_SELECTED.get("name", ""),
            "sample_id": GLOBAL_SELECTED.get("sample_id", ""),
            "sample_desc": GLOBAL_SELECTED.get("description", ""),
            "sample_set": GLOBAL_SELECTED.get("group", ""),
        }
        _md.update(md)
        return (yield from func(*args, md=_md, **kwargs))

    return _inner


def _sst_add_comment(func):
    @merge_func(func)
    def _inner(*args, md=None, comment=None, group_name=None, **kwargs):
        """
        Parameters
        ----------
        comment : str, optional
            A comment that will be added into the run metadata. If not provided, no comment will be added.
        group_name : str, optional
            A group name label that will be added into the run metadata.
        """
        md = md or {}
        if comment is not None:
            _md = {"comment": comment}
        else:
            _md = {}
        if group_name is not None:
            _md["group_name"] = group_name
        _md.update(md)
        return (yield from func(*args, md=_md, **kwargs))

    return _inner


def sst_base_scan_decorator(func):
    @repeat
    @_beamline_setup
    @_sst_setup_detectors
    @_sst_add_sample_md
    @_sst_add_plot_md
    @_sst_add_comment
    @merge_func(func)
    def _inner(*args, **kwargs):
        return (yield from func(*args, **kwargs))

    return _inner


def sst_add_bl_prefix(func):
    base_name = func.__name__
    plan_name = f"{settings.beamline_prefix}_{base_name}"
    func.__name__ = plan_name
    return func
    
def wrap_plan_name(func):
    return wrap_metadata({"plan_name": func.__name__})(func)
    
def sst_builtin_scan_wrapper(func):
    """
    Designed to wrap bluesky built-in scans to produce an sst version
    """
    @wrap_plan_name
    @sst_add_bl_prefix
    @sst_base_scan_decorator
    @merge_func(func)
    def _inner(*args, **kwargs):
        return (yield from func(*args, **kwargs))

    # _inner = wrap_metadata({"plan_name": plan_name})(sst_base_scan_decorator(func))

    d = f"""Modifies {func.__name__} to automatically fill
dets with global active beamline detectors.
Other detectors may be added on the fly via extra_dets
---------------------------------------------------------
"""

    _inner.__doc__ = d + _inner.__doc__
    return _inner
