from bluesky.preprocessors import SupplementalData
from .queueserver import GLOBAL_USER_STATUS
from .status import StatusDict
from .hw import HardwareGroup, DetectorGroup, _load_hardware
from os.path import join, exists

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


_default_settings = {
    "device_filename": "devices.toml",
    "beamline_filename": "beamline.toml",
}


class BeamlineModel:
    default_groups = [
        "shutters",
        "gatevalves",
        "apertures",
        "pinholes",
        "gauges",
        "motors",
        "detectors",
        "manipulators",
        "mirrors",
        "controllers",
        "vacuum",
        "misc",
    ]

    default_roles = [
        "beam_current",
        "beam_status",
        "default_shutter",
        "energy",
        "intensity_detector",
        "primary_sampleholder",
        "reference_sampleholder",
        "slits",
    ]

    reserved = [
        "current_sample",
        "samples",
        "config",
        "groups",
        "roles",
        "supplemental_data",
        "devices",
        "redis",
    ]

    def __init__(self, *args, **kwargs):
        """
        Creates an empty BeamlineModel, need to load_devices after init
        """
        self.supplemental_data = SupplementalData()
        self.settings = StatusDict()
        self.devices = StatusDict()
        self.energy = None
        self.primary_sampleholder = None
        self.default_shutter = None
        self.config = {}
        self.groups = list(self.default_groups)
        self.roles = list(self.default_roles)
        self.detectors = DetectorGroup("detectors")
        self.motors = HardwareGroup("motors")

        # Initialize empty dictionaries for each default group
        for group in self.default_groups:
            if not hasattr(self, group):
                setattr(self, group, HardwareGroup(group))

        for role in self.default_roles:
            if not hasattr(self, role):
                setattr(self, role, None)

    def load_settings(self, settings_file):
        """
        Load settings from a TOML file.

        Parameters
        ----------
        settings_file : str
            The path to the settings file.
        """
        settings_dict = {}
        settings_dict.update(_default_settings)

        if not exists(settings_file):
            print("No settings found, using defaults")
            config = {}
        else:
            with open(settings_file, "rb") as f:
                config = tomllib.load(f)
        settings_dict.update(config.get("settings", {}))
        self.settings.update(settings_dict)
        print(f"Loading Settings {self.settings}")

    def load_beamline(self, startup_dir, ns=None):
        """
        Load and configure the beamline from the startup directory.

        Parameters
        ----------
        startup_dir : str
            Directory containing configuration files
        ns : dict, optional
            Namespace for loading devices
        """
        settings_file = join(startup_dir, "beamline.toml")
        self.load_settings(settings_file)
        self.settings["startup_dir"] = startup_dir
        object_file = join(startup_dir, self.settings["device_filename"])
        beamline_file = join(startup_dir, self.settings["beamline_filename"])

        with open(beamline_file, "rb") as f:
            beamline_config = tomllib.load(f)

        devices, groups, roles = _load_hardware(object_file, ns, load_pass="auto")
        self.config.update(beamline_config)
        self.load_redis()
        tmp_settings = GLOBAL_USER_STATUS.request_status_dict(
            "SETTINGS", use_redis=True
        )
        tmp_settings.update(self.settings)
        self.settings = tmp_settings
        print(f"Settings from Redis: {self.settings}")
        self.load_devices(devices, groups, roles, beamline_config)

    def load_devices(self, devices, groups, roles, config):
        self.config.update(config)
        self.devices.update(devices)
        for groupname, devicelist in groups.items():
            self._configure_group(groupname, devicelist)
        print(roles)
        for role, key in roles.items():
            if role in self.reserved:
                raise KeyError(f"Key {role} is reserved, use a different role name")
            if role != "":
                if role not in self.roles:
                    self.roles.append(role)
                print(f"Setting {role} to {key}")
                setattr(self, role, devices[key])
            if role == "primary_sampleholder":
                self.primary_sampleholder.samples = (
                    GLOBAL_USER_STATUS.request_status_dict(
                        "GLOBAL_SAMPLES", use_redis=True
                    )
                )
                self.primary_sampleholder.current_sample = (
                    GLOBAL_USER_STATUS.request_status_dict(
                        "GLOBAL_SELECTED", use_redis=True
                    )
                )
                self.samples = self.primary_sampleholder.samples
                self.current_sample = self.primary_sampleholder.current_sample
            elif role == "reference_sampleholder":
                self.reference_sampleholder.samples = (
                    GLOBAL_USER_STATUS.request_status_dict(
                        "REFERENCE_SAMPLES", use_redis=True
                    )
                )
                self.reference_sampleholder.current_sample = (
                    GLOBAL_USER_STATUS.request_status_dict(
                        "REFERENCE_SELECTED", use_redis=True
                    )
                )

    def load_redis(self):
        redis_settings = (
            self.config.get("settings", {}).get("redis", {}).get("info", {})
        )
        self.redis_settings = redis_settings
        if redis_settings:
            GLOBAL_USER_STATUS.init_redis(
                host=redis_settings["host"],
                port=redis_settings.get("port", None),
                db=redis_settings.get("db", 0),
                global_prefix=redis_settings.get("prefix", ""),
            )

    def get_device(self, device_name, get_subdevice=True):
        """
        If get_subdevice, follow dotted device names and return the deepest device.
        If False, follow the parents and return the overall parent device
        """
        device_parts = device_name.split(".")
        device = self.devices[device_parts[0]]
        if get_subdevice:
            for subdev in device_parts[1:]:
                device = getattr(device, subdev)
        else:
            while device.parent is not None:
                device = device.parent
        return device

    def add_to_baseline(self, device_or_name, only_subdevice=False):
        if isinstance(device_or_name, str):
            device = self.get_device(device_or_name, only_subdevice)
        else:
            device = device_or_name
        if device not in self.supplemental_data.baseline:
            self.supplemental_data.baseline.append(device)

    def _configure_group(self, groupname, devicelist):
        if groupname in self.reserved:
            raise KeyError(f"Key {groupname} is reserved, use a different group name")

        configuration = self.config.get("configuration", {})
        all_device_config = self.config.get("devices", {})
        group_baseline = groupname in configuration.get("baseline", [])

        if groupname not in self.groups:
            self.groups.append(groupname)
            setattr(self, groupname, HardwareGroup(groupname))
        group = getattr(self, groupname)
        for key in devicelist:
            device_config = all_device_config.get(key, {})
            print(f"Setting {groupname}[{key}]")
            device = self.devices[key]
            group.add(key, device, **device_config)
            should_add_to_baseline = all_device_config.get(key, {}).get(
                "baseline", group_baseline
            )
            if should_add_to_baseline:
                self.add_to_baseline(key, False)


GLOBAL_BEAMLINE = BeamlineModel()
