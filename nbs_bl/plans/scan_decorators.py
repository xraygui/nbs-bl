from functools import wraps
from ..beamline import GLOBAL_BEAMLINE
from ..detectors import (
    activate_detector,
    deactivate_detector,
    activate_detector_set,
)
from ..utils import merge_func
from .plan_stubs import set_exposure, sampleholder_set_sample, sampleholder_move_sample
from bluesky.plan_stubs import mv, trigger_and_read, declare_stream
from bluesky.utils import separate_devices
from bluesky.preprocessors import stage_wrapper, plan_mutator, set_run_key_wrapper
from .preprocessors import wrap_metadata
from .suspenders import dynamic_suspenders
from .groups import repeat

# from ..settings import settings
from typing import Optional
from importlib.metadata import entry_points
from functools import reduce


def wrap_scantype(scantype):
    def decorator(func):
        return wrap_metadata({"scantype": scantype})(func)

    return decorator


def _beamline_setup(func):
    blconf = GLOBAL_BEAMLINE.config.get("configuration", {})
    if blconf.get("has_slits", False):
        func = _slit_setup(func)
    if blconf.get("has_motorized_samples", False):
        func = _sample_setup_with_move(func)
    else:
        func = _sample_setup_no_move(func)
    func = _eref_setup(func)
    func = _energy_setup(func)
    return func


def _eref_setup(func):
    @merge_func(func)
    def _inner(
        *args, eref_sample: Optional[str] = None, md: Optional[dict] = None, **kwargs
    ):
        """
        Parameters
        ----------
        eref_sample : str, optional
            The energy reference sample. If given, the selected reference sample is set
        """
        md = md or {}
        _md = {}
        blconf = GLOBAL_BEAMLINE.config.get("configuration", {})
        if eref_sample is not None and blconf.get("has_motorized_eref", False):
            yield from sampleholder_move_sample(
                GLOBAL_BEAMLINE.reference_sampleholder, eref_sample
            )

            _md.update({"reference_sample": eref_sample})
        _md.update(md)
        return (yield from func(*args, md=_md, **kwargs))

    return _inner


def _sample_setup_with_move(func):
    @merge_func(func)
    def _inner(
        *args,
        sample: Optional[str] = None,
        sample_position: Optional[dict] = {},
        **kwargs,
    ):
        """
        Parameters
        ----------
        sample : str, optional
            The sample id. If given, the selected sample metadata is set
        sample_position: dict, optional
            A dictionary of positions relative to the sample center. Parameters not given will be assumed to
            be the default for the sampleholder (typically moving the sample into the beam at a typical angle)
        """
        if sample is not None:
            yield from sampleholder_move_sample(
                GLOBAL_BEAMLINE.primary_sampleholder, sample, **sample_position
            )
        return (yield from func(*args, **kwargs))

    return _inner


def _sample_setup_no_move(func):
    @merge_func(func)
    def _inner(*args, sample=None, **kwargs):
        """
        Parameters
        ----------
        sample : str, optional
            The sample id. If given, the selected sample metadata is set, but the sample is not moved
        """
        if sample is not None:
            yield from sampleholder_set_sample(
                GLOBAL_BEAMLINE.primary_sampleholder, sample
            )
        return (yield from func(*args, **kwargs))

    return _inner


def _slit_setup(func):
    @merge_func(func)
    def _inner(*args, eslit: Optional[float] = None, **kwargs):
        """
        Parameters
        ----------
        eslit : float, optional
            If not None, will set the beamline exit slit prior to the plan start.
        """
        if eslit is not None:
            yield from mv(GLOBAL_BEAMLINE.slits, eslit)
        return (yield from func(*args, **kwargs))

    return _inner


def _energy_setup(func):
    @merge_func(func)
    def _inner(
        *args,
        energy: Optional[float] = None,
        polarization: Optional[float] = None,
        **kwargs,
    ):
        """
        Parameters
        ----------
        energy : float, optional
            If not None, will set the beamline energy prior to the plan start.
        """
        if energy is not None:
            yield from mv(GLOBAL_BEAMLINE.energy, energy)
        if polarization is not None and hasattr(GLOBAL_BEAMLINE, "polarization"):
            yield from mv(GLOBAL_BEAMLINE.polarization, polarization)
        return (yield from func(*args, **kwargs))

    return _inner


def staged_baseline_wrapper(plan, devices, name="staged_baseline"):
    """
    Preprocessor that records a baseline of all `devices` after `open_run`

    The readings are designated for a separate event stream named 'baseline' by
    default.

    Parameters
    ----------
    plan : iterable or iterator
        a generator, list, or similar containing `Msg` objects
    devices : collection
        collection of Devices to read
        If None, the plan passes through unchanged.
    name : string, optional
        name for event stream; by default, 'baseline'

    Yields
    ------
    msg : Msg
        messages from plan, with 'set' messages inserted
    """

    def head():
        yield from declare_stream(*devices, name=name)
        yield from trigger_and_read(devices, name=name)

    def tail():
        yield from trigger_and_read(devices, name=name)

    def insert_baseline(msg):
        if msg.command == "open_run":
            if msg.run is not None:
                return None, set_run_key_wrapper(head(), msg.run)
            else:
                return None, head()

        elif msg.command == "close_run":
            if msg.run is not None:
                return set_run_key_wrapper(tail(), msg.run), None
            else:
                return tail(), None

        return None, None

    if not devices:
        # no-op
        return (yield from plan)
    else:
        return (yield from plan_mutator(plan, insert_baseline))


def _nbs_setup_detectors_with_baseline(func):
    @merge_func(func, ["detectors"])
    def _inner(*args, extra_dets=[], dwell: Optional[float] = None, **kwargs):
        """
        Parameters
        ----------
        extra_dets : list, optional
            A list of extra detectors to be activated for the scan, by default [].
        dwell : float, optional
            The exposure time in seconds for all detectors, by default None.
            If None, do not set any exposure time, and assume that detectors are already set
        """

        # for det in extra_dets:
        #    activate_detector(det)
        print("Detector Setup Decorator with Baseline")
        if dwell is not None:
            yield from set_exposure(dwell, extra_dets=extra_dets)

        all_dets = separate_devices(GLOBAL_BEAMLINE.detectors.active + extra_dets)
        # We need to stage only the baseline devices that are not already in the list of detectors
        # In order to avoid double staging
        if hasattr(GLOBAL_BEAMLINE, "staged_baseline"):
            staged_baseline_devices = separate_devices(
                GLOBAL_BEAMLINE.staged_baseline.values()
            )
            devices_to_stage = [
                dev for dev in staged_baseline_devices if dev not in all_dets
            ]
        else:
            staged_baseline_devices = []
            devices_to_stage = []

        def inner():
            yield from func(all_dets, *args, **kwargs)

        ret = yield from stage_wrapper(
            staged_baseline_wrapper(inner(), staged_baseline_devices), devices_to_stage
        )

        # for det in extra_dets:
        #    deactivate_detector(det)

        return ret

    return _inner


def _nbs_setup_detectors(func):
    @merge_func(func, ["detectors"])
    def _inner(*args, extra_dets=[], dwell: Optional[float] = None, **kwargs):
        """
        Parameters
        ----------
        extra_dets : list, optional
            A list of extra detectors to be activated for the scan, by default [].
        dwell : float, optional
            The exposure time in seconds for all detectors, by default None.
            If None, do not set any exposure time, and assume that detectors are already set
        """

        # for det in extra_dets:
        #    activate_detector(det)
        print("Detector Setup Decorator")
        if dwell is not None:
            yield from set_exposure(dwell, extra_dets=extra_dets)
        all_dets = GLOBAL_BEAMLINE.detectors.active + extra_dets
        ret = yield from func(all_dets, *args, **kwargs)

        # for det in extra_dets:
        #    deactivate_detector(det)

        return ret

    return _inner


def _nbs_add_plot_md(func):
    @merge_func(func)
    def _inner(*args, md: Optional[dict] = None, plot_detectors: list = None, **kwargs):
        md = md or {}
        plot_hints = {}
        if plot_detectors is not None:
            activate_detector_set(plot_detectors)
        plot_hints = GLOBAL_BEAMLINE.detectors.get_plot_hints()
        _md = {"plot_hints": plot_hints}
        _md.update(md)
        return (yield from func(*args, md=_md, **kwargs))

    return _inner


def _nbs_add_sample_md(func):
    @merge_func(func)
    def _inner(*args, md: Optional[dict] = None, **kwargs):
        """
        Sample information is automatically added to the run md
        """
        md = md or {}
        if hasattr(GLOBAL_BEAMLINE, "current_sample"):
            _md = {
                "sample_name": GLOBAL_BEAMLINE.current_sample.get("name", ""),
                "sample_id": GLOBAL_BEAMLINE.current_sample.get("sample_id", ""),
                "sample_desc": GLOBAL_BEAMLINE.current_sample.get("description", ""),
                "sample_set": GLOBAL_BEAMLINE.current_sample.get("group", ""),
                "sample_info": {
                    k: v
                    for k, v in GLOBAL_BEAMLINE.current_sample.items()
                    if k not in ["name", "sample_id", "description", "group"]
                },
            }
            _md.update(md)
            return (yield from func(*args, md=_md, **kwargs))
        else:
            return (yield from func(*args, md=md, **kwargs))

    return _inner


def _nbs_add_comment(func):
    @merge_func(func)
    def _inner(
        *args,
        md: Optional[dict] = None,
        comment: Optional[str] = None,
        group_name: Optional[str] = None,
        **kwargs,
    ):
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


def nbs_base_scan_decorator(func):
    @repeat
    @_beamline_setup
    @_nbs_setup_detectors
    @_nbs_add_sample_md
    @_nbs_add_plot_md
    @_nbs_add_comment
    @merge_func(func)
    def _inner(*args, **kwargs):
        return (yield from func(*args, **kwargs))

    return _inner


"""
    This was too clever, and was a mistake
def nbs_add_bl_prefix(func):
    base_name = func.__name__
    plan_name = f"{settings.beamline_prefix}_{base_name}"
    func.__name__ = plan_name
    return func
"""


def wrap_plan_name(func):
    return wrap_metadata({"plan_name": func.__name__})(func)


def nbs_builtin_scan_wrapper(func):
    """
    Designed to wrap bluesky built-in scans to produce an nbs version
    """

    @wrap_plan_name
    @nbs_base_scan_decorator
    @merge_func(func)
    def _inner(*args, **kwargs):
        print("Running ", func.__name__)
        return (yield from func(*args, **kwargs))

    # _inner = wrap_metadata({"plan_name": plan_name})(nbs_base_scan_decorator(func))

    d = f"""Modifies {func.__name__} to automatically fill
dets with global active beamline detectors.
Other detectors may be added on the fly via extra_dets
---------------------------------------------------------
"""

    _inner.__doc__ = d + _inner.__doc__
    return _inner


def get_decorator_entrypoints():
    """
    Get decorator entrypoints from beamline configuration.

    Returns
    -------
    list
        List of decorator functions loaded from entrypoints
    """
    config = GLOBAL_BEAMLINE.config
    decorator_entrypoints = config.get("settings", {}).get("plan_decorators", [])

    decorators = []
    if decorator_entrypoints:
        eps = entry_points()
        for ep_name in decorator_entrypoints:
            try:
                # Look for entrypoint in nbs_bl.plan_decorators group
                matches = eps.select(group="nbs_bl.plan_decorators", name=ep_name)
                for match in matches:
                    decorator = match.load()
                    decorators.append(decorator)
            except Exception as e:
                print(f"Failed to load decorator {ep_name}: {e}")

    return decorators


def dynamic_scan_wrapper(func):
    """
    A flexible wrapper for Bluesky scans that incorporates base NBS functionality
    and additional decorators from entrypoints.

    Parameters
    ----------
    func : callable
        The scan function to wrap

    Returns
    -------
    callable
        Wrapped scan function with all decorators applied
    """
    # Get base decorators
    base_decorators = [merge_func(func), dynamic_suspenders, nbs_base_scan_decorator]

    # Get additional decorators from entrypoints
    additional_decorators = get_decorator_entrypoints()

    # Combine all decorators
    all_decorators = base_decorators + additional_decorators + [wrap_plan_name]

    # Apply decorators in order
    def _inner(*args, **kwargs):
        print("Running ", func.__name__)
        return (yield from func(*args, **kwargs))

    # Apply all decorators in sequence
    wrapped = reduce(lambda f, dec: dec(f), all_decorators, _inner)

    # Add documentation
    d = f"""Wraps {func.__name__} with additional arguments and default detectors.

Other detectors may be added on the fly via extra_dets


Additional decorators loaded:
{[d.__name__ for d in additional_decorators]}
"""
    wrapped.__doc__ = d + (wrapped.__doc__ or "")

    return wrapped
