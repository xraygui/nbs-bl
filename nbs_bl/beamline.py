from bluesky.preprocessors import SupplementalData
from .queueserver import GLOBAL_USER_STATUS
from .status import StatusDict
from .hw import HardwareGroup, DetectorGroup, loadFromConfig
from nbs_core.autoload import instantiateOphyd, _find_deferred_devices, getMaxLoadPass
from os.path import join, exists
import IPython

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
        self.md = {}
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

        # Storage for deferred devices
        self._deferred_config = {}
        self._deferred_devices = set()

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

    def load_configuration(self, startup_dir):
        """
        Load and merge configuration files.

        Parameters
        ----------
        startup_dir : str
            Directory containing configuration files

        Returns
        -------
        dict
            Device configuration dictionary
        """
        object_file = join(startup_dir, self.settings["device_filename"])
        beamline_file = join(startup_dir, self.settings["beamline_filename"])

        with open(beamline_file, "rb") as f:
            beamline_config = tomllib.load(f)

        with open(object_file, "rb") as f:
            object_config = tomllib.load(f)

        # Store merged configuration
        self.config.update(beamline_config)
        self.config["devices"] = object_config

        # Handle Redis settings
        self.load_redis()
        self.load_md()
        tmp_settings = GLOBAL_USER_STATUS.request_status_dict(
            "SETTINGS", use_redis=True
        )
        tmp_settings.update(self.settings)
        self.settings = tmp_settings
        print(f"Settings from Redis: {self.settings}")

        return object_config

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
        # Phase 1: Load settings
        settings_file = join(startup_dir, "beamline.toml")
        self.load_settings(settings_file)
        self.settings["startup_dir"] = startup_dir

        # Phase 2: Load and merge configurations
        object_config = self.load_configuration(startup_dir)

        # Phase 3: Load and register devices
        self.load_devices(object_config, ns)

    def register_devices(self, devices, groups, roles):
        """
        Handle device registration and grouping.

        Parameters
        ----------
        devices : dict
            Dictionary of instantiated devices
        groups : dict
            Dictionary mapping group names to lists of device names
        roles : dict
            Dictionary mapping role names to device names
        """
        self.devices.update(devices)

        for groupname, devicelist in groups.items():
            self._configure_group(groupname, devicelist)

        for role, key in roles.items():
            self._configure_role(role, key)

    def _configure_role(self, role, key):
        """
        Handle role assignment and special device setup.

        Parameters
        ----------
        role : str
            Role name to configure
        key : str
            Device key to assign to the role
        """
        if role in self.reserved:
            raise KeyError(f"Key {role} is reserved, use a different role name")
        if role != "":
            if role not in self.roles:
                self.roles.append(role)
            print(f"Setting {role} to {key}")
            setattr(self, role, self.devices[key])

    def handle_special_devices(self, roles):
        """
        Handle special device setup, particularly sampleholders.

        Parameters
        ----------
        roles : dict
            Dictionary mapping role names to device names
        """
        if "primary_sampleholder" in roles:
            self._setup_sampleholder(
                self.primary_sampleholder,
                "GLOBAL_SAMPLES",
                "GLOBAL_SELECTED",
                is_primary=True,
            )
        if "reference_sampleholder" in roles:
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

    def load_devices(self, config, ns=None, load_pass=None):
        """
        Load and register devices from configuration.

        Parameters
        ----------
        config : dict
            Device configuration dictionary
        ns : dict, optional
            Namespace for loading devices
        """
        if load_pass is None:
            max_load_pass = getMaxLoadPass(config)
            for pass_num in range(1, max_load_pass + 1):
                self.load_devices(config, ns, load_pass=pass_num)
        # Find deferred devices for tracking
        _, _, deferred_config = _find_deferred_devices(config)

        # Load non-deferred devices
        devices, groups, roles = loadFromConfig(
            config, instantiateOphyd, alias=True, namespace=ns, load_pass=load_pass
        )

        # Update deferred device tracking
        if deferred_config:
            self._deferred_config.update(deferred_config)
            self._deferred_devices.update(deferred_config.keys())
        # Remove loaded devices from deferred tracking
        for device_name in devices:
            self._deferred_config.pop(device_name, None)
            self._deferred_devices.discard(device_name)

        # Register devices and handle special cases
        self.register_devices(devices, groups, roles)
        self.handle_special_devices(roles)

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
            # Load the device using the main loading function
            self.load_devices(self._deferred_config, ns)

            return self.devices.get(device_name)
        except Exception as e:
            raise RuntimeError(f"Failed to load device {device_name}: {e}") from e

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

    def load_md(self):
        redis_md_settings = (
            self.config.get("settings", {}).get("redis", {}).get("md", {})
        )
        if redis_md_settings:
            import redis
            from nbs_bl.status import RedisStatusDict

            mdredis = redis.Redis(
                redis_md_settings["host"],
                port=redis_md_settings.get("port", 6379),
                db=redis_md_settings.get("db", 0),
            )
            self.md = RedisStatusDict(
                mdredis, prefix=redis_md_settings.get("prefix", "")
            )
            GLOBAL_USER_STATUS.add_status("USER_MD", self.md)

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
                "_baseline", group_baseline
            )
            if should_add_to_baseline:
                self.add_to_baseline(key, False)

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


GLOBAL_BEAMLINE = BeamlineModel()
