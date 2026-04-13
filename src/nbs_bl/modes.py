from .beamline import GLOBAL_BEAMLINE as bl
from .help import add_to_func_list

@add_to_func_list
def activate_mode(mode):
    """Activate a mode"""
    bl.activate_mode(mode)

@add_to_func_list
def deactivate_mode(mode):
    """Deactivate a mode"""
    bl.deactivate_mode(mode)