from bluesky import RunEngine
from bluesky.plan_stubs import mv, mvr, abs_set
from bluesky.plan_stubs import mv as move
from .detectors import (list_detectors,
                        activate_detector, deactivate_detector,
                        plot_detector, unplot_detector)
from .motors import (add_motor, list_motors,
                     remove_motor)
from .plans.groups import group
from .queueserver import request_update, get_status
from .help import GLOBAL_IMPORT_DICTIONARY, sst_help
from .re_commands import load_RE_commands

for key in GLOBAL_IMPORT_DICTIONARY:
    if key not in globals():
        globals()[key] = GLOBAL_IMPORT_DICTIONARY[key]

RE = RunEngine(call_returns_result=True)
load_RE_commands(RE)

sst_help()
