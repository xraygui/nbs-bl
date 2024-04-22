from ophyd import Device
from .help import add_to_func_list
from .printing import boxed_text
from .globalVars import (
    GLOBAL_ACTIVE_DETECTORS,
    GLOBAL_DETECTOR_STATUS,
    GLOBAL_DETECTORS,
    GLOBAL_DETECTOR_DESCRIPTIONS,
    GLOBAL_PLOT_DETECTORS,
    GLOBAL_DETECTOR_SETS,
    GLOBAL_DETECTOR_THRESHOLDS,
    GLOBAL_HARDWARE,
)
from .utils import iterfy


def add_detector(
    det, description="", name=None, activate=True, sets=None, threshold=None, **kwargs
):
    """Add a detector to the global detector buffer

    with an optional description, and an optional name to substitute
    for the detector's built-in name

    Parameters
    ----------
    det : Ophyd device
        A detector to add to the buffer
    description : str
        An optional string that identifies the detector
    name : str
        a string to use as a key, instead of det.name
    activate : bool
        Whether to add the detector to the active detectors list

    Returns
    -------
    name : str
        The key used to insert the detector into the detector list
    """
    if name is None:
        name = det.name
    GLOBAL_DETECTORS[name] = det
    GLOBAL_DETECTOR_STATUS[name] = "inactive"
    GLOBAL_DETECTOR_DESCRIPTIONS[name] = description
    if activate:
        activate_detector(name)
    if sets is not None:
        for set_name, role in sets.items():
            add_detector_to_set(det, role, set_name)
    if threshold is not None:
        GLOBAL_DETECTOR_THRESHOLDS[det.name] = threshold
    return name


@add_to_func_list
def list_detectors(describe=False):
    """List all global detectors, optionally provide text descriptions

    Parameters
    ----------
    describe : Bool
        If True, print the text description of each detector

    """
    title = "Detectors"
    text = []
    for name, det in GLOBAL_DETECTORS.items():
        if det in GLOBAL_ACTIVE_DETECTORS:
            status = "active"
        else:
            status = "inactive"
        """
        if role, det in GLOBAL_PLOT_DETECTORS:
            plotted = "plotted"
        else:
            plotted = "not plotted"
        """
        text.append(f"{name}: {status}")
        if describe:
            text.append(f"    {GLOBAL_DETECTOR_DESCRIPTIONS[name]}")
    boxed_text(title, text, "white")


def get_detector(det_or_name):
    """

    Given either a name, or a detector instance, return a detector
    instance. If given a name, return the corresponding detector from
    GLOBAL_DETECTORS.

    Parameters
    ----------
    det_or_name : str or Device
        A name of a detector in GLOBAL_DETECTORS, or a detector
        instance

    Raises
    ------
    KeyError
        If a name is passed that is not in GLOBAL_DETECTORS

    Returns
    -------
    A detector instance

    """
    if isinstance(det_or_name, Device):
        return det_or_name
    elif det_or_name in GLOBAL_DETECTORS:
        return GLOBAL_DETECTORS[det_or_name]
    else:
        raise KeyError(f"Detector {det_or_name} not found in GLOBAL_DETECTORS")


def get_name(det_or_name):
    if det_or_name in GLOBAL_DETECTORS:
        return det_or_name
    for name, det in GLOBAL_DETECTORS.items():
        if det == det_or_name:
            return name
    raise KeyError(f"Detector name {det_or_name} not found in GLOBAL_DETECTORS")


@add_to_func_list
def activate_detector(det_or_name, role=None):
    """Activate a detector so that is is measured by default

    Parameters
    ----------
    det_or_name : device or str
        Either a device, or the name of a device in the global
        detector buffer

    """
    # Todo: take a list
    detector = get_detector(det_or_name)
    name = get_name(det_or_name)
    if GLOBAL_DETECTOR_STATUS[name] == "disabled":
        print(f"Detector {name} is disabled, and will not be activated!")
        return
    else:
        GLOBAL_DETECTOR_STATUS[name] = "active"
    if detector not in GLOBAL_ACTIVE_DETECTORS:
        GLOBAL_ACTIVE_DETECTORS.append(detector)
    if role is not None:
        plot_detector(detector, role)


@add_to_func_list
def disable_detector(det_or_name):
    """Disable a detector so that it is not measured, and will not be activated

    Parameters
    ----------
    det_or_name : device or str
        Either a device, or the name of a device in the global
        detector buffer

    """
    deactivate_detector(det_or_name)
    name = get_name(det_or_name)
    GLOBAL_DETECTOR_STATUS[name] = "disabled"


@add_to_func_list
def enable_detector(det_or_name, activate=True):
    """Enable a detector so that it can be activated

    Parameters
    ----------
    det_or_name : device or str
        Either a device, or the name of a device in the global
        detector buffer
    activate : Bool
        If True, also activate the detector when it is enabled
    """

    detector = get_detector(det_or_name)
    name = get_name(det_or_name)
    GLOBAL_DETECTOR_STATUS[name] = "inactive"
    if activate:
        activate_detector(detector)


@add_to_func_list
def deactivate_detector(det_or_name):
    """Deactivate a detector so that it is not measured by default

    Parameters
    ----------
    det_or_name : device or str
        Either a device, or the name of a device in the global
        detector buffer

    """

    detector = get_detector(det_or_name)
    name = get_name(det_or_name)
    if GLOBAL_DETECTOR_STATUS[name] != "disabled":
        GLOBAL_DETECTOR_STATUS[name] = "inactive"
    if detector in GLOBAL_ACTIVE_DETECTORS:
        idx = GLOBAL_ACTIVE_DETECTORS.index(detector)
        GLOBAL_ACTIVE_DETECTORS.pop(idx)
    unplot_detector(detector)


@add_to_func_list
def plot_detector(det_or_name, role):
    """Add a detector to a specified plot role

    Parameters
    ----------
    det_or_name: device or string
        Either a device, or the name of a device in the global
        detector buffer
    roles : string
        "primary", "normalization", "reference" or "auxiliary"
    """
    detector = get_detector(det_or_name)
    unplot_detector(detector)
    GLOBAL_PLOT_DETECTORS[role].append(detector)


@add_to_func_list
def unplot_detector(det_or_name):
    """
    Parameters
    ----------
    det_or_name: device or string
        Either a device, or the name of a device in the global
        detector buffer
    """
    detector = get_detector(det_or_name)
    for role_list in GLOBAL_PLOT_DETECTORS.values():
        if detector in role_list:
            idx = role_list.index(detector)
            role_list.pop(idx)


def remove_detector(det_or_name):
    """Remove a detector from the global detector buffer entirely

    Parameters
    ----------
    det_or_name : device or str
        Either a device, or the name of a device in the global
        detector buffer

    Raises
    ------
    KeyError
        Detector not found in the global buffer

    """
    detector = get_detector(det_or_name)
    deactivate_detector(detector)
    if hasattr(det_or_name, "name"):
        name = det_or_name.name
    else:
        name = det_or_name
    if name not in GLOBAL_DETECTORS:
        name = None
        for k, v in GLOBAL_DETECTORS.items():
            if v == det_or_name:
                name = k
                break
    if name is None:
        raise KeyError(
            f"Detector {det_or_name} not found in global counters dictionary"
        )

    del GLOBAL_DETECTORS[name]
    del GLOBAL_DETECTOR_STATUS[name]
    del GLOBAL_DETECTOR_DESCRIPTIONS[name]


def add_detector_set(
    name, primary=[], auxiliary=[], normalization=[], reference=[], inactive=[]
):
    det_set = {}
    det_set["primary"] = [get_detector(det_or_name) for det_or_name in iterfy(primary)]
    det_set["auxiliary"] = [
        get_detector(det_or_name) for det_or_name in iterfy(auxiliary)
    ]
    det_set["normalization"] = [
        get_detector(det_or_name) for det_or_name in iterfy(normalization)
    ]
    det_set["reference"] = [
        get_detector(det_or_name) for det_or_name in iterfy(reference)
    ]
    det_set["inactive"] = [
        get_detector(det_or_name) for det_or_name in iterfy(inactive)
    ]
    GLOBAL_DETECTOR_SETS[name] = det_set


def add_detector_to_set(det_or_name, role, set_name):
    detector = get_detector(det_or_name)
    if set_name not in GLOBAL_DETECTOR_SETS:
        GLOBAL_DETECTOR_SETS[set_name] = {}
    if role not in GLOBAL_DETECTOR_SETS[set_name]:
        GLOBAL_DETECTOR_SETS[set_name][role] = []
    GLOBAL_DETECTOR_SETS[set_name][role].append(detector)


def save_current_detectors_as_set(name):
    GLOBAL_DETECTOR_SETS[name] = {}
    GLOBAL_DETECTOR_SETS[name].update(GLOBAL_PLOT_DETECTORS)


@add_to_func_list
def activate_detector_set(name):
    GLOBAL_PLOT_DETECTORS.clear()
    GLOBAL_PLOT_DETECTORS.update(GLOBAL_DETECTOR_SETS[name])
    for role in GLOBAL_DETECTOR_SETS[name]:
        if role != "inactive":
            for det in GLOBAL_DETECTOR_SETS[name][role]:
                activate_detector(det)
        else:
            for det in GLOBAL_DETECTOR_SETS[name][role]:
                deactivate_detector(det)


@add_to_func_list
def list_detector_sets():
    for set_name in GLOBAL_DETECTOR_SETS.keys():
        print(f"{set_name}")
        for role in GLOBAL_DETECTOR_SETS[set_name]:
            print(
                f"{role}: {[get_name(det) for det in GLOBAL_DETECTOR_SETS[set_name][role]]}"
            )


@add_to_func_list
def list_plotted_detectors():
    for role in GLOBAL_PLOT_DETECTORS:
        print(f"Detectors in role {role}")
        for det in GLOBAL_PLOT_DETECTORS[role]:
            print(f"{get_name(det)}")
