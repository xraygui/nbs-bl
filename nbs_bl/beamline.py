from bluesky.preprocessors import SupplementalData
from .status import StatusDict
from .hw import HardwareGroup, DetectorGroup


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

    def __init__(self, *args, **kwargs):
        """
        Creates an empty BeamlineModel, need to load_devices after init
        """
        self.supplemental_data = SupplementalData()
        self.devices = StatusDict()
        self.energy = None
        self.primary_manipulator = None
        self.default_shutter = None
        self.config = {}
        self.groups = list(self.default_groups)  # Create a copy of the default groups
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

    def load_devices(self, devices, groups, roles, config):
        self.config.update(config)
        self.devices.update(devices)
        for groupname, devicelist in groups.items():
            self._configure_group(groupname, devicelist)
        print(roles)
        for role, key in roles.items():
            if role != "":
                self.roles.append(role)
                print(f"Setting {role} to {key}")
                setattr(self, role, devices[key])

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
