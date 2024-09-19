from .status import StatusList, StatusDict
from .queueserver import add_status
from bluesky.preprocessors import SupplementalData
from .beamline import BeamlineModel

GLOBAL_BEAMLINE = BeamlineModel()
GLOBAL_SETTINGS = StatusDict()
add_status("SETTINGS", GLOBAL_SETTINGS)
GLOBAL_SAMPLES = StatusDict()
GLOBAL_SELECTED = StatusDict()

add_status("SAMPLE_LIST", GLOBAL_SAMPLES)
add_status("SAMPLE_SELECTED", GLOBAL_SELECTED)

GLOBAL_XAS_PLANS = StatusDict()

add_status("XAS_PLANS", GLOBAL_XAS_PLANS)

GLOBAL_PLAN_LIST = StatusList()
GLOBAL_SCAN_LIST = StatusList()

add_status("PLAN_LIST", GLOBAL_PLAN_LIST)
add_status("SCAN_LIST", GLOBAL_SCAN_LIST)
# GLOBAL_SUPPLEMENTAL_DATA = SupplementalData()
# GLOBAL_HARDWARE = StatusDict()
# GLOBAL_CONFIG_GROUPS = StatusDict()

# GLOBAL_DETECTORS = GLOBAL_BEAMLINE.detectors.devices
# GLOBAL_DETECTOR_DESCRIPTIONS = GLOBAL_BEAMLINE.detectors.descriptions
# GLOBAL_DETECTOR_STATUS = GLOBAL_BEAMLINE.detectors.status
# GLOBAL_ACTIVE_DETECTORS = GLOBAL_BEAMLINE.detectors.active
# GLOBAL_PLOT_DETECTORS = StatusDict()
# # GLOBAL_DETECTOR_SETS = StatusDict()
# # GLOBAL_DETECTOR_THRESHOLDS = StatusDict()
# # GLOBAL_ALIGNMENT_DETECTOR = StatusDict()

# add_status("ACTIVE_DETECTORS", GLOBAL_ACTIVE_DETECTORS)
# add_status("DETECTOR_DESCRIPTIONS", GLOBAL_DETECTOR_DESCRIPTIONS)
# add_status("DETECTORS", GLOBAL_DETECTORS)
# add_status("DETECTOR_STATUS", GLOBAL_DETECTOR_STATUS)
# add_status("PLOT_DETECTORS", GLOBAL_PLOT_DETECTORS)

# GLOBAL_MOTORS = GLOBAL_BEAMLINE.motors.devices
# GLOBAL_MOTOR_DESCRIPTIONS = GLOBAL_BEAMLINE.motors.descriptions

# add_status("MOTORS", GLOBAL_MOTORS)
# add_status("MOTOR_DESCRIPTIONS", GLOBAL_MOTOR_DESCRIPTIONS)


# GLOBAL_SHUTTERS = StatusDict()
# GLOBAL_MIRRORS = StatusDict()
# GLOBAL_DEFAULT_SHUTTER = StatusList()

# GLOBAL_MANIPULATOR = StatusDict()

# GLOBAL_GATEVALVES = StatusDict()
# GLOBAL_ENERGY = StatusDict()

# Need to make this more uniform to fit with plans & scans
