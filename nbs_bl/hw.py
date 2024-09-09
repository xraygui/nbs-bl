from .status import StatusDict, StatusList
from .queueserver import add_status
from nbs_core.autoload import loadFromConfig, instantiateOphyd
from .printing import boxed_text


try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


def _load_hardware(config_file, namespace=None):
    print(f"Attempting to load objects in {config_file}")
    with open(config_file, "rb") as f:
        config = tomllib.load(f)
    devices, groups, roles = loadFromConfig(
        config, instantiateOphyd, alias=True, namespace=namespace
    )
    for key, dev in devices.items():
        globals()[key] = dev
    return devices, groups, roles


class HardwareGroup:
    def __init__(self, name=""):
        self.groupname = name
        self.devices = StatusDict()
        self.descriptions = StatusDict()
        add_status(self.groupname.upper(), self.devices)
        add_status(self.groupname.upper() + "_DESCRIPTIONS", self.descriptions)

    def values(self):
        return self.devices.values()

    def items(self):
        return self.devices.items()

    def get_key(self, device_or_key):
        if isinstance(device_or_key, str):
            if device_or_key in self.devices:
                return device_or_key
            else:
                raise KeyError(f"Device {device_or_key} not found")
        else:
            for k, v in self.devices.items():
                if v == device_or_key:
                    return k
        raise KeyError(f"Device {device_or_key} not found")

    def get(self, device_or_key):
        key = self.get_key(device_or_key)
        return self.devices[key]

    def add(self, key, device, description="", **kwargs):
        self.devices[key] = device
        self.descriptions[key] = description

    def remove(self, device_or_key):
        key = self.get_key(device_or_key)
        self.devices.pop(key)
        self.descriptions.pop(key)

    def describe(self, verbose=True, textFunction=None):
        title = self.groupname
        text = []
        for key, device in self.devices.items():
            name = device.name
            if textFunction is None:
                text.append(f"Key: {key}; Name: {name}")
            else:
                text.append(textFunction(key, device))
            if verbose:
                text.append(f"    {self.descriptions[key]}")
        boxed_text(title, text, "white")


class DetectorGroup(HardwareGroup):
    def __init__(self, name="detectors"):
        super().__init__(name=name)
        self.status = StatusDict()
        self.thresholds = StatusDict()
        self.active = StatusList()
        self.roles = {}
        add_status(self.groupname.upper() + "_STATUS", self.status)
        add_status(self.groupname.upper() + "_ACTIVE", self.active)

    def add(
        self,
        key,
        device,
        description="",
        activate=True,
        sets=None,
        threshold=None,
        **kwargs,
    ):
        super().add(key, device, description)
        self.status[key] = "inactive"
        if activate:
            self.activate(key)
        if sets is not None:
            for set_name in sets:
                self.add_to_set(device, set_name)
        if threshold is not None:
            self.thresholds[key] = threshold

    def activate(self, device_or_key, role=None):
        key = self.get_key(device_or_key)
        detector = self.devices[key]
        if self.status[key] == "disabled":
            print(f"Detector {key} is disabled and will not be activated")
            return
        else:
            self.status[key] = "active"
        if detector not in self.active:
            self.active.append(detector)
        if role is not None:
            self.add_role(key, role)

    def deactivate(self, device_or_key):
        key = self.get_key(device_or_key)
        device = self.get(device_or_key)
        if device in self.active:
            idx = self.active.index(device)
            self.active.pop(idx)
        if self.status[key] != "disabled":
            self.status[key] = "inactive"

    def activate_set(self, set_name):
        for key in self.detector_sets.get(set_name, []):
            self.activate(key)

    def deactivate_set(self, set_name):
        for key in self.detector_sets.get(set_name, []):
            self.deactivate(key)

    def add_set(self, set_name, set_keys):
        self.detector_sets[set_name] = set_keys

    def set_role(self, key, role):
        self.roles[key] = role

    def save_active_as_set(self, set_name):
        set_keys = [self.get_key(device) for device in self.active]
        self.add_set(set_name, set_keys)

    def enable(self, device_or_key, activate=True):
        key = self.get_key(device_or_key)
        self.status[key] = "inactive"
        if activate:
            self.activate(device_or_key)

    def disable(self, device_or_key):
        key = self.get_key(device_or_key)
        self.deactivate(device_or_key)
        self.status[key] = "disabled"

    def get_plot_hints(self):
        plot_hints = {}
        for detector in self.active:
            key = self.get_key(detector)
            role = self.roles.get(key, "auxiliary")
            if role not in plot_hints:
                plot_hints[role] = []
            if hasattr(detector, "get_plot_hints"):
                plot_hints[role] += detector.get_plot_hints()
            else:
                plot_hints[role].append(detector.name)
        return plot_hints
