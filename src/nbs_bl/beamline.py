from bluesky.preprocessors import SupplementalData
from .queueserver import GLOBAL_USER_STATUS
from .status import StatusDict
from .hw import HardwareGroup, DetectorGroup, loadDevices
from nbs_core.autoload import instantiateOphyd, _find_deferred_devices

import IPython


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
        "RE",
        "md",
    ]

    def __init__(self, *args, **kwargs):
        """
        Creates an empty BeamlineModel.

        The model is a pure data structure. Use BeamlineInitializer
        to initialize it from configuration files.
        """
        print("Initializing beamline model")
        self.reset()

    def add_device(self, device_name, device_info):
        """
        Add a device to the beamline model.

        Parameters
        ----------
        device_name : str
            Name of the device
        device_info : dict
            Dictionary containing the following keys:
            - device: The device object
            - loaded: Whether the device is loaded
            - groups: List of groups the device is in
            - roles: List of roles the device is in
        """
        # print(f"Adding device {device_name} to beamline model: {device_info}")
        self._add_device_to_modes(device_name, device_info)
        if not device_info["loaded"]:
            self._deferred_devices.add(device_name)
            self._deferred_config[device_name] = device_info["config"]
            return

        self.devices[device_name] = device_info["device"]
        self._add_device_to_groups(device_name, device_info)
        self._set_device_roles(device_name, device_info)

    def _add_device_to_modes(self, device_name, device_info):
        modes = device_info["config"].get("_modes", [])
        for mode in modes:
            if mode in self.modes:
                self.modes[mode].append(device_name)
            else:
                self.modes[mode] = [device_name]

    def _set_device_roles(self, device_name, device_info):
        """
        Handle role assignment and special device setup.

        Parameters
        ----------
        role : str
            Role name to configure
        key : str
            Device key to assign to the role
        """
        roles = device_info["roles"]
        for role in roles:
            if role in self.reserved:
                raise KeyError(f"Key {role} is reserved, use a different role name")
            if role != "":
                if role not in self.roles:
                    self.roles.append(role)
                print(f"Setting {role} to {device_name}")
                setattr(self, role, self.devices[device_name])

    def handle_special_devices(self):
        """
        Handle special device setup, particularly sampleholders.

        Parameters
        ----------
        roles : dict
            Dictionary mapping role names to device names
        """
        self._setup_sampleholder(
            self.primary_sampleholder,
            "GLOBAL_SAMPLES",
            "GLOBAL_SELECTED",
            is_primary=True,
        )
        if "reference_sampleholder" in self.roles:
            self._setup_sampleholder(
                self.reference_sampleholder,
                "REFERENCE_SAMPLES",
                "REFERENCE_SELECTED",
                is_primary=False,
            )

    def _setup_sampleholder(self, holder, samples_key, current_key, is_primary=False):
        """
        Set up a sampleholder with Redis data.

        Parameters
        ----------
        holder : object
            The sampleholder device to set up
        samples_key : str
            Redis key for samples data
        current_key : str
            Redis key for current sample data
        is_primary : bool, optional
            Whether this is the primary sampleholder
        """
        if holder is None:
            return
        
        tmp_samples = GLOBAL_USER_STATUS.request_status_dict(
            samples_key, use_redis=True
        )
        tmp_samples.update(holder.samples)
        holder.samples = tmp_samples

        tmp_current = GLOBAL_USER_STATUS.request_status_dict(
            current_key, use_redis=True
        )
        tmp_current.update(holder.current_sample)
        holder.current_sample = tmp_current

        if is_primary:
            self.samples = holder.samples
            self.current_sample = holder.current_sample

        try:
            holder.reload_sample_frames()
        except Exception as e:
            print(f"Error reloading sample frames for primary sampleholder: {e}")

    def activate_mode(self, modes):
        if not isinstance(modes, (list, tuple)):
            modes = [modes]
        all_devices = set(self.devices.keys())
        devices_to_defer = set()
        devices_to_load = set()
        for mode, mode_devices in self.modes.items():
            if mode in modes:
                devices_to_load.update(mode_devices)
            else:
                devices_to_defer.update(mode_devices)
        devices_to_defer.difference_update(devices_to_load)
        devices_to_defer &= all_devices
        devices_to_load.difference_update(all_devices)

        for device_name in devices_to_defer:
            self.defer_device(device_name)
        for device_name in devices_to_load:
            self.load_deferred_device(device_name)

    def deactivate_mode(self, modes):
        if not isinstance(modes, (list, tuple)):
            modes = [modes]
        devices_to_defer = set()
        for mode in modes:
            if mode in self.modes:
                for device_name in self.modes[mode]:
                    devices_to_defer.add(device_name)
        for device_name in devices_to_defer:
            self.defer_device(device_name)

    def load_deferred_device(self, device_name, ns=None):
        """
        Load a specific deferred device and its dependencies.
        If an alias is requested, loads its root device.

        Parameters
        ----------
        device_name : str
            Name of the device to load

        Returns
        -------
        object
            The loaded device

        Raises
        ------
        KeyError
            If the device is not in the deferred devices list
        RuntimeError
            If loading the device fails
        """
        if device_name not in self._deferred_devices:
            raise KeyError(f"Device {device_name} is not in deferred devices")

        # If it's an alias, get and load the root device
        config = self._deferred_config.get(device_name, {})
        if isinstance(config, dict) and "_alias" in config:
            root_device = config["_alias"].split(".")[0]
            if root_device != device_name:  # Prevent recursion
                return self.load_deferred_device(root_device, ns)

        # Create config with just this device and its dependencies
        self._deferred_config[device_name]["_defer_loading"] = False

        try:
            devices = loadDevices(
                self._deferred_config,
                namespace=ns,
                mode=None,
            )
            for device_name, device_info in devices.items():
                self.add_device(device_name, device_info)

            for device_name in devices:
                self._deferred_config.pop(device_name, None)
                self._deferred_devices.discard(device_name)

            return self.devices.get(device_name)
        except Exception as e:
            raise RuntimeError(f"Failed to load device {device_name}: {e}") from e


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

    def _add_device_to_groups(self, device_key, device_info):
        groups = device_info["groups"]
        # print(f"Adding device {device_key} to groups: {groups}")
        for groupname in groups:
            if groupname in self.reserved:
                raise KeyError(f"Key {groupname} is reserved, use a different group name")
            if groupname not in self.groups:
                self.groups.append(groupname)
                setattr(self, groupname, HardwareGroup(groupname))
            group = getattr(self, groupname)
            group.add(device_key, device_info["device"], **device_info["config"])
            # print(f"Setting {groupname}[{device_key}]")

    def get_deferred_devices(self):
        """Return set of currently deferred devices."""
        return self._deferred_devices.copy()

    def is_device_deferred(self, device_name):
        """Check if a device is currently deferred."""
        return device_name in self._deferred_devices

    def defer_device(self, device_name):
        """
        Move a loaded device to deferred state.

        Parameters
        ----------
        device_name : str
            Name of the device to defer

        Raises
        ------
        KeyError
            If the device is not loaded or already deferred
        RuntimeError
            If the device cannot be deferred
        """
        ip = IPython.get_ipython()

        if device_name in self._deferred_devices:
            print(
                f"Device {device_name} is already deferred, continuing to check aliased devices"
            )

        # Get device's configuration
        device_config = self.config["devices"].get(device_name)
        if not device_config:
            raise RuntimeError(f"No configuration found for device {device_name}")

        # Update configuration to defer loading
        device_config["_defer_loading"] = True

        deferred_devices, _, deferred_config = _find_deferred_devices(
            self.config["devices"]
        )

        self._deferred_config.update(deferred_config)
        self._deferred_devices.update(deferred_devices)

        # Remove from groups
        for newly_deferred in deferred_devices:
            if newly_deferred not in self.devices:
                continue
            for group in self.groups:
                group_obj = getattr(self, group)
                if newly_deferred in group_obj.devices:
                    group_obj.remove(newly_deferred)

            # Remove from roles
            for role in self.roles:
                if hasattr(self, role) and getattr(self, role) == self.devices.get(
                    newly_deferred, None
                ):
                    setattr(self, role, None)

            # Remove from baseline if present
            device = self.devices.get(newly_deferred, None)
            if device != None and device in self.supplemental_data.baseline:
                self.supplemental_data.baseline.remove(device)

            # Remove from devices registry
            if device != None:
                self.devices.pop(newly_deferred)
                del device
            ip.user_global_ns.pop(newly_deferred, None)
        return device_name

    def __getitem__(self, key):
        """Allow dictionary-like access to devices."""
        return self.devices[key]

    def __setitem__(self, key, value):
        """Allow dictionary-like setting of devices."""
        self.devices[key] = value

    def reset(self):
        """
        Reset the beamline model to an uninitialized state.

        Clears all devices, configuration, settings, and other initialized
        data while preserving the structure. Useful for debugging and testing.
        """
        
        self.initialized = False
        self.supplemental_data = SupplementalData()
        self.md = {}
        self.RE = None
        self.settings = StatusDict()
        self.devices = StatusDict()
        self.config = {}
        self.plan_status = {}
        self._deferred_config = {}
        self._deferred_devices = set()

        self.groups = list(self.default_groups)
        self.roles = list(self.default_roles)

        self.modes = {}
        if hasattr(self, "samples"):
            delattr(self, "samples")
        if hasattr(self, "current_sample"):
            delattr(self, "current_sample")
        if hasattr(self, "redis_settings"):
            delattr(self, "redis_settings")


    def _initialize_groups(self):
        print("Initializing groups")
        for group in self.default_groups:
            setattr(self, group, HardwareGroup(group))

        for role in self.default_roles:
            setattr(self, role, None)

        self.detectors = DetectorGroup("detectors")
        self.motors = HardwareGroup("motors")



    def reset_old(self):
        self.supplemental_data = SupplementalData()
        self.md = {}
        self.RE = None
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
        self.plan_status = {}

        self._deferred_config = {}
        self._deferred_devices = set()

        for group in self.default_groups:
            if not hasattr(self, group):
                setattr(self, group, HardwareGroup(group))

        for role in self.default_roles:
            if not hasattr(self, role):
                setattr(self, role, None)

GLOBAL_BEAMLINE = BeamlineModel()
