from .help import add_to_func_list
from .globalVars import GLOBAL_BEAMLINE


def get_active_detectors():
    return GLOBAL_BEAMLINE.detectors.active


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
    GLOBAL_BEAMLINE.detectors.activate(det_or_name, role)


@add_to_func_list
def list_detectors(verbose=False):
    """List all global detectors, optionally provide text descriptions

    Parameters
    ----------
    describe : Bool
        If True, print the text description of each detector

    """

    def textFunction(group, key, device):
        text = f"{key}: {device.name}; {group.status[key]}"
        return text

    GLOBAL_BEAMLINE.detectors.describe(verbose, textFunction)


@add_to_func_list
def disable_detector(det_or_name):
    """Disable a detector so that it is not measured, and will not be activated

    Parameters
    ----------
    det_or_name : device or str
        Either a device, or the name of a device in the global
        detector buffer

    """
    GLOBAL_BEAMLINE.detectors.disable(det_or_name)


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

    GLOBAL_BEAMLINE.detectors.enable(det_or_name, activate)


@add_to_func_list
def deactivate_detector(det_or_name):
    """Deactivate a detector so that it is not measured by default

    Parameters
    ----------
    det_or_name : device or str
        Either a device, or the name of a device in the global
        detector buffer

    """

    GLOBAL_BEAMLINE.detectors.deactivate(det_or_name)


@add_to_func_list
def activate_detector_set(name):
    GLOBAL_BEAMLINE.detectors.activate_set(name)
