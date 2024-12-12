from bluesky.plan_stubs import abs_set
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

from nbs_bl.help import GLOBAL_IMPORT_DICTIONARY
from nbs_bl.plans.groups import group
from nbs_bl.queueserver import request_update, get_status
from nbs_bl.samples import list_samples
from nbs_bl.beamline import GLOBAL_BEAMLINE


for key in GLOBAL_IMPORT_DICTIONARY:
    if key not in globals():
        globals()[key] = GLOBAL_IMPORT_DICTIONARY[key]


def main():
    print("NBS Startup")

    RE = create_run_engine(setup=True)
    RE = setup_run_engine(RE)

    if "redis" in GLOBAL_BEAMLINE.settings:
        import redis
        from nbs_bl.status import RedisStatusDict
        from nbs_bl.queueserver import GLOBAL_USER_STATUS

        redis_settings = GLOBAL_BEAMLINE.settings.get("redis").get("md")
        uri = redis_settings.get("host", "localhost")  # "info.sst.nsls2.bnl.gov"
        prefix = redis_settings.get("prefix", "")
        md = RedisStatusDict(redis.Redis(uri), prefix=prefix)
        GLOBAL_USER_STATUS.add_status("USER_MD", md)
        RE.md = md

    RE(set_exposure(1.0))

    # load_saved_configuration()
    activate_detector_set("default")
