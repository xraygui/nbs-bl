from bluesky.plan_stubs import abs_set, mv
import nbs_bl
from nbs_bl.hw import *
from nbs_bl.detectors import (
    list_detectors,
    activate_detector,
    deactivate_detector,
    activate_detector_set,
)
from nbs_bl.motors import list_motors
import nbs_bl.plans.scans

from nbs_bl.run_engine import setup_run_engine, create_run_engine

from nbs_bl.plans.groups import group
from nbs_bl.plans.plan_stubs import set_exposure
from nbs_bl.queueserver import request_update, get_status
from nbs_bl.samples import list_samples
from nbs_bl.beamline import GLOBAL_BEAMLINE


print("NBS Startup")

RE(set_exposure(1.0))

# load_saved_configuration()
activate_detector_set("default")
