import os
from importlib.util import find_spec
from importlib.metadata import entry_points
from .beamline import GLOBAL_BEAMLINE, BeamlineModel
from .queueserver import request_update, get_status, GLOBAL_USER_STATUS
from .run_engine import create_run_engine
from .hw import loadDevices
from abc import ABC, abstractmethod
from os.path import join, exists
from .tiledWriter import subscribe_tiled_profile
from nbs_core.autoconf import load_settings
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


def get_startup_dir():
    """
    Get the IPython startup directory.

    Returns
    -------
    str
        The path to the IPython startup directory.
    """
    ip = get_ipython()
    startup_dir = ip.profile_dir.startup_dir
    return startup_dir

def get_default_initializer():
    ip = get_ipython()
    if ip.user_ns.get("beamline_initializer") is None:
        ip.user_ns["beamline_initializer"] = BeamlineInitializer(GLOBAL_BEAMLINE)
    return ip.user_ns["beamline_initializer"]

def load_and_configure_everything(startup_dir=None, initializer=None):
    """
    Load and configure all necessary hardware and settings for the beamline.

    Parameters
    ----------
    startup_dir : str, optional
        The directory from which to load configuration files.
        If not specified, uses the IPython startup directory.
    """
    if startup_dir is None:
        startup_dir = get_startup_dir()

    ip = get_ipython()
    ip.user_ns["get_status"] = get_status
    ip.user_ns["request_update"] = request_update

    if initializer is None:
        initializer = get_default_initializer()
    initializer.initialize(startup_dir, ip.user_ns)


class InitializationStep(ABC):
    """
    Base class for initialization steps.

    Each step is independent and can be extended or customized.
    Steps execute in sequence and share a context dictionary.
    Steps can declare dependencies on other step classes.
    """

    def __init__(self):
        self.substep_iterator = (chr(i) for i in range(ord("a"), ord("z") + 1))

    @abstractmethod
    def execute(self, beamline: BeamlineModel, context: dict) -> dict:
        """
        Execute this initialization step.

        Parameters
        ----------
        beamline : BeamlineModel
            The beamline model to initialize
        context : dict
            Shared context between steps (startup_dir, namespace, etc.)

        Returns
        -------
        dict
            Updated context (may add new keys for subsequent steps)
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Human-readable name for this step.

        Returns
        -------
        str
            Step name for logging and identification
        """
        pass

    @property
    def depends_on(self) -> list[type]:
        """
        List of step classes that must be completed before this step can run.

        Returns
        -------
        list[type]
            List of InitializationStep subclasses that are dependencies.
            Default is an empty list (no dependencies).
        """
        return []

    def print_substep(self, message: str):
        try:
            substep = next(self.substep_iterator)
        except StopIteration:
            substep = "-"
        print(f"  Substep {substep}: {message}")

    def print_status(self, status: str):
        print(f"  {self.name}: {status}")

class BlockStep(InitializationStep):

    @property
    def name(self) -> str:
        return "Blocking"

    def execute(self, beamline: BeamlineModel, context: dict) -> dict:
        raise RuntimeError("Stopping initialization for testing")

class LoadSettingsStep(InitializationStep):
    """Load settings from beamline.toml"""

    @property
    def name(self) -> str:
        return "Load Settings"

    def execute(self, beamline: BeamlineModel, context: dict) -> dict:
        _default_settings = {
            "device_filename": "devices.toml",
            "beamline_filename": "beamline.toml",
            "sim_filename": "sim_conf.toml",
        }
        startup_dir = context["startup_dir"]
        settings_file = join(startup_dir, context.get("beamline_filename", _default_settings["beamline_filename"]))

        settings_dict = {}
        settings_dict.update(_default_settings)

        sim_mode = os.environ.get("NBS_SIM_MODE", "0")
        if sim_mode == "1":
            sim_mode = True
        else:
            sim_mode = False

        if sim_mode:
            print("**********************************************************")
            print("*                                                        *")
            print("*                    SIMULATION MODE                     *")
            print("*           Using simulated devices and plans            *")
            print("*                                                        *")
            print("**********************************************************")

        if not exists(settings_file):
            self.print_status("No settings found, using defaults")
            config = {}
        else:
            config = load_settings(settings_file, sim_mode=sim_mode)

        settings_dict.update(config.get("settings", {}))
        beamline.settings.update(settings_dict)
        beamline.settings["startup_dir"] = startup_dir
        beamline.settings["sim_mode"] = sim_mode
        context["sim_mode"] = sim_mode

        # self.print_status(f"Settings: {beamline.settings}")
        return context


class LoadConfigurationFilesStep(InitializationStep):
    """Load and merge device and beamline configuration files"""

    @property
    def name(self) -> str:
        return "Load Configuration Files"

    @property
    def depends_on(self) -> list[type]:
        return [LoadSettingsStep]

    def execute(self, beamline: BeamlineModel, context: dict) -> dict:
        startup_dir = context["startup_dir"]
        sim_mode = context["sim_mode"]
        device_file = join(startup_dir, beamline.settings["device_filename"])
        beamline_file = join(startup_dir, beamline.settings["beamline_filename"])

        
        beamline_config = load_settings(beamline_file, sim_mode=sim_mode)
        device_config = load_settings(device_file, sim_mode=sim_mode)

        beamline.config.update(beamline_config)
        beamline.config["devices"] = device_config

        context["device_config"] = device_config
        return context

class UserInitializationHook(InitializationStep):
    """User initialization hook"""

    @property
    def name(self) -> str:
        return "User Initialization Hook"

    @property
    def depends_on(self) -> list[type]:
        return [LoadSettingsStep]

    def execute(self, beamline: BeamlineModel, context: dict) -> dict:
        modules = beamline.settings.get("initialization_modules", [])
        ip = get_ipython()

        for module_name in modules:
            module_path = find_spec(module_name).origin
            self.print_substep(f"Trying to import {module_name} from {module_path}")
            ip.run_line_magic("run", module_path)

        return context


class InitializeRedisStep(InitializationStep):
    """Initialize Redis connections"""

    @property
    def name(self) -> str:
        return "Initialize Redis"

    @property
    def depends_on(self) -> list[type]:
        return [LoadConfigurationFilesStep]

    def execute(self, beamline: BeamlineModel, context: dict) -> dict:
        redis_settings = (
            beamline.config.get("settings", {})
            .get("redis", {})
            .get("info", {})
        )

        beamline.redis_settings = redis_settings

        if redis_settings:
            GLOBAL_USER_STATUS.init_redis(redis_settings)

            tmp_settings = GLOBAL_USER_STATUS.request_status_dict(
                "SETTINGS", use_redis=True
            )
            tmp_settings.update(beamline.settings)
            beamline.settings = tmp_settings
            # self.print_status(f"Settings from Redis: {beamline.settings}")

        beamline.plan_status = GLOBAL_USER_STATUS.request_status_dict(
            "PLAN_STATUS", use_redis=True
        )

        return context


class InitializeMetadataStep(InitializationStep):
    """Initialize metadata Redis connection"""

    @property
    def name(self) -> str:
        return "Initialize Metadata"

    def execute(self, beamline: BeamlineModel, context: dict) -> dict:
        redis_md_settings = (
            beamline.config.get("settings", {})
            .get("redis", {})
            .get("md", {})
        )

        if redis_md_settings:
            from nbs_bl.redisUtils import open_redis_client_from_settings
            from nbs_bl.status import RedisStatusDict
            from nbs_bl.redisDevice import _RedisSignal

            mdredis = open_redis_client_from_settings(redis_md_settings)
            beamline.md = RedisStatusDict(
                mdredis, prefix=redis_md_settings.get("prefix", "")
            )
            GLOBAL_USER_STATUS.add_status("USER_MD", beamline.md)
            _RedisSignal.set_default_status_provider(GLOBAL_USER_STATUS)
        else:
            beamline.md = GLOBAL_USER_STATUS.request_status_dict("USER_MD")
            _RedisSignal.set_default_status_provider(GLOBAL_USER_STATUS)

        context["namespace"].update({"md": beamline.md})

        return context

class InitializeRunEngineStep(InitializationStep):
    """Initialize the run engine"""

    @property
    def name(self) -> str:
        return "Initialize Run Engine"

    @property
    def depends_on(self) -> list[type]:
        return [InitializeMetadataStep]

    def execute(self, beamline: BeamlineModel, context: dict) -> dict:
        self.print_substep("Creating run engine")
        beamline.run_engine = create_run_engine(setup=True)

        beamline.run_engine.md = beamline.md
        context["namespace"].update({"RE": beamline.run_engine})

        tiled_cfg = (
            beamline.settings.get("tiled_writer", {})
        )
        if tiled_cfg and tiled_cfg.get("enabled", True):
            self.print_substep("Subscribing to Tiled writer")
            client = subscribe_tiled_profile(beamline.run_engine, tiled_cfg)
            context["namespace"]["tiled_writing_client"] = client

        kafka_cfg = (beamline.settings.get("kafka", {}))
        if kafka_cfg and kafka_cfg.get("enabled", True):
            from nslsii import configure_kafka_publisher

            name = kafka_cfg.get("name")
            kafka_file = kafka_cfg.get("config_file", None)
            self.print_substep(f"Subscribing to Kafka topic: {name}")
            if kafka_file is not None:
                configure_kafka_publisher(beamline.run_engine, name, override_config_path=kafka_file)
            else:
                configure_kafka_publisher(beamline.run_engine, name)
        zmq_cfg = beamline.settings.get("zmq", {})
        if zmq_cfg and zmq_cfg.get("enabled", True):
            from bluesky.callbacks.zmq import Publisher
            hostname = zmq_cfg.get("hostname", "localhost")
            port = zmq_cfg.get("port", 5577)
            self.print_substep(f"Subscribing to ZMQ publisher at {hostname}:{port}")
            publisher = Publisher(f"{hostname}:{port}")
            beamline.run_engine.subscribe(publisher)

        return context

class InitializeLoggingStep(InitializationStep):
    """Initialize logging"""

    @property
    def name(self) -> str:
        return "Initialize Logging"

    def execute(self, beamline: BeamlineModel, context: dict) -> dict:

        logging_config = beamline.settings.get("logging", {})

        if logging_config.get("enabled", True) and logging_config.get("method", "nslsii") == "nslsii":

            from nslsii import configure_bluesky_logging, configure_ipython_logging
            from nslsii.common.ipynb.logutils import log_exception
            import logging

            self.print_substep("Configuring nslsii logging")
            configure_bluesky_logging(ipython=get_ipython())
            configure_ipython_logging(exception_logger=log_exception, ipython=get_ipython())

            possible_loggers = ["bluesky", "caproto", "ophyd", "nslsii"]
            for logger_name in possible_loggers:
                individual_log_config = logging_config.get(logger_name, {})
                if individual_log_config:
                    logger = logging.getLogger(logger_name)
                    level = individual_log_config.get("level", None)
                    if level:
                        logger.setLevel(level)

        return context

class LoadDevicesStep(InitializationStep):
    """Load devices from configuration (multi-pass)"""

    @property
    def name(self) -> str:
        return "Load Devices"
    
    @property
    def depends_on(self) -> list[type]:
        return [LoadConfigurationFilesStep]

    def execute(self, beamline: BeamlineModel, context: dict) -> dict:
        device_config = beamline.config["devices"]
        beamline._initialize_groups()
        ns = context.get("namespace")
        # Move all of this to a helper function in hw.py
        devices = loadDevices(device_config, ns, mode="default")

        

        for device_name, device_info in devices.items():
            beamline.add_device(device_name, device_info)

        context["devices"] = devices
        return context


class SetupSpecialDevicesStep(InitializationStep):
    """Setup special devices like sampleholders"""

    @property
    def name(self) -> str:
        return "Setup Special Devices"

    @property
    def depends_on(self) -> list[type]:
        return [LoadDevicesStep]

    def execute(self, beamline: BeamlineModel, context: dict) -> dict:
        beamline.handle_special_devices()

        return context


class UserStartupHook(InitializationStep):
    """Configure modules"""

    @property
    def name(self) -> str:
        return "Configure Startup Modules"

    @property
    def depends_on(self) -> list[type]:
        return [LoadSettingsStep]

    def execute(self, beamline: BeamlineModel, context: dict) -> dict:
        modules = beamline.settings.get("startup_modules", [])
        ip = get_ipython()

        for module_name in modules:
            module_path = find_spec(module_name).origin
            self.print_substep(f"Trying to import {module_name} from {module_path}")
            ip.run_line_magic("run", module_path)

        return context

class LoadPlansStep(InitializationStep):
    """Load plans from configuration files"""

    @property
    def name(self) -> str:
        return "Load Plans"

    @property
    def depends_on(self) -> list[type]:
        return [UserStartupHook]

    def execute(self, beamline: BeamlineModel, context: dict) -> dict:
        """
        Load all plans using registered entry points.

        Parameters
        ----------
        startup_dir : str
            Directory containing plan configuration files
        """
        startup_dir = context["startup_dir"]
        plan_settings = beamline.settings.get("plans", {})
        self.print_status(f"Loading plans from {startup_dir}")
        # Iterate through all registered plan loaders
        for entry_point in entry_points(group="nbs_bl.plan_loaders"):
            plan_type = entry_point.name
            plan_files = plan_settings.get(plan_type, [])

            if not plan_files:
                print(f"No {plan_type} plans found")
                continue
            self.print_substep(f"Loading {plan_type} plans from {plan_files}")
            # Load the plan loader function
            plan_loader = entry_point.load()

            # Load each plan file for this plan type
            for plan_file in plan_files:
                full_path = join(startup_dir, plan_file)
                try:
                    plan_loader(full_path)
                    # print(f"Loaded {plan_type} plans from {plan_file}")
                except Exception as e:
                    print(f"Error loading {plan_type} plans from {plan_file}: {str(e)}")

        return context

class InitializeGlobalNamespaceStep(InitializationStep):
    """Initialize the global namespace"""

    @property
    def name(self) -> str:
        return "Initialize Global Namespace"

    @property
    def depends_on(self) -> list[type]:
        return [InitializeRunEngineStep]

    def execute(self, beamline: BeamlineModel, context: dict) -> dict:
        from nbs_bl.help import GLOBAL_IMPORT_DICTIONARY

        for key in GLOBAL_IMPORT_DICTIONARY:
            if key not in context["namespace"]:
                context["namespace"][key] = GLOBAL_IMPORT_DICTIONARY[key]
        return context


class BeamlineInitializer:
    """
    Orchestrates the initialization pipeline.

    Manages the order and execution of initialization steps.
    Tracks which steps have been completed to support partial initialization.
    """

    def __init__(self, beamline: BeamlineModel):
        """
        Initialize the initializer with a beamline model.

        Parameters
        ----------
        beamline : BeamlineModel
            The beamline model to initialize
        """
        self.beamline = beamline
        self.steps: list[InitializationStep] = []
        self._completed_steps: set[int] = set()
        self._completed_step_classes: set[type] = set()
        self._context: dict = {}
        self._register_default_steps()

    def _register_default_steps(self):
        """Register the default initialization steps in order."""
        self.steps = [
            LoadSettingsStep(),
            LoadConfigurationFilesStep(),
            InitializeLoggingStep(),
            UserInitializationHook(),
            InitializeRedisStep(),
            InitializeMetadataStep(),
            InitializeRunEngineStep(),
            LoadDevicesStep(),
            SetupSpecialDevicesStep(),
            UserStartupHook(),
            LoadPlansStep(),
            InitializeGlobalNamespaceStep(),
        ]

    def list_steps(self) -> list[str]:
        """
        List the names of all steps in the initialization pipeline.

        Returns
        -------
        list[str]
            Names of all steps in the pipeline
        """
        return [step.name for step in self.steps]

    def add_step(
        self, step: InitializationStep, after: str = None, before: str = None
    ):
        """
        Add a custom initialization step.

        Parameters
        ----------
        step : InitializationStep
            The step to add
        after : str, optional
            Insert after step with this name
        before : str, optional
            Insert before step with this name

        Raises
        ------
        ValueError
            If both after and before are specified, or if the reference step is not found
        """
        if after and before:
            raise ValueError("Cannot specify both 'after' and 'before'")

        if after:
            try:
                idx = next(i for i, s in enumerate(self.steps) if s.name == after)
                self.steps.insert(idx + 1, step)
            except StopIteration:
                raise ValueError(f"Step '{after}' not found")

        elif before:
            try:
                idx = next(i for i, s in enumerate(self.steps) if s.name == before)
                self.steps.insert(idx, step)
            except StopIteration:
                raise ValueError(f"Step '{before}' not found")
        else:
            self.steps.append(step)

    def remove_step(self, step_name: str) -> None:
        """
        Remove a step from the initialization pipeline.

        Parameters
        ----------
        step_name : str
            The name of the step to remove
        """
        try:
            idx = next(i for i, s in enumerate(self.steps) if s.name == step_name)
            self.steps.pop(idx)
        except StopIteration:
            raise ValueError(f"Step '{step_name}' not found")

    def replace_step(self, step: InitializationStep, old_step: str) -> None:
        """
        Replace a step with a new step.

        Parameters
        ----------
        step : InitializationStep
            The new step to replace the old step
        old_step : str
            The name of the step to replace

        Raises
        ------
        ValueError
            If the step is not found or has already been completed
        """
        try:
            idx = next(i for i, s in enumerate(self.steps) if s.name == old_step)
        except StopIteration:
            raise ValueError(f"Step '{old_step}' not found")

        if idx in self._completed_steps:
            raise ValueError(
                f"Cannot replace step '{old_step}' - it has already been completed. "
                f"Use reset() to clear completed steps first."
            )

        self.steps[idx] = step

    def get_completed_steps(self) -> list[str]:
        """
        Get a list of completed step names.

        Returns
        -------
        list[str]
            Names of steps that have been completed
        """
        return [self.steps[i].name for i in sorted(self._completed_steps)]

    def _check_dependencies(self, step: InitializationStep) -> tuple[bool, list[type]]:
        """
        Check if all dependencies for a step are satisfied.

        A dependency is satisfied if any completed step class is a subclass of
        (or is) the required dependency class. This allows custom steps that
        inherit from dependency classes to satisfy dependencies.

        Parameters
        ----------
        step : InitializationStep
            The step to check dependencies for

        Returns
        -------
        tuple[bool, list[type]]
            Tuple of (all_satisfied, missing_dependencies)
        """
        dependencies = step.depends_on
        missing = []
        
        for dep_class in dependencies:
            satisfied = False
            for completed_class in self._completed_step_classes:
                if issubclass(completed_class, dep_class):
                    satisfied = True
                    break
            if not satisfied:
                missing.append(dep_class)
        
        return len(missing) == 0, missing

    def get_next_step_index(self) -> int:
        """
        Get the index of the next step to be initialized.

        Returns
        -------
        int
            Index of the next uninitialized step with satisfied dependencies,
            or -1 if all steps are complete or no step has satisfied dependencies
        """
        for i in range(len(self.steps)):
            if i not in self._completed_steps:
                step = self.steps[i]
                deps_satisfied, _ = self._check_dependencies(step)
                if deps_satisfied:
                    return i
        return -1

    def get_next_step_name(self) -> str:
        """
        Get the name of the next step to be initialized.

        Returns
        -------
        str
            Name of the next uninitialized step, or None if all steps are complete
        """
        idx = self.get_next_step_index()
        if idx == -1:
            return None
        return self.steps[idx].name

    def initialize_next_step(self, startup_dir: str = None, ns: dict = None) -> tuple[str, dict]:
        """
        Initialize the next uninitialized step.

        Parameters
        ----------
        startup_dir : str, optional
            Directory containing configuration files. Only needed for first step.
        ns : dict, optional
            Namespace for loading devices. Only needed for first step.

        Returns
        -------
        tuple[str, dict]
            Tuple of (step_name, context) after executing the step

        Raises
        ------
        RuntimeError
            If the step fails to execute
        ValueError
            If startup_dir is not provided and this is the first step
        """
        idx = self.get_next_step_index()
        if idx == -1:
            raise ValueError("All steps have been completed")

        if not self._context:
            if startup_dir is None:
                raise ValueError("startup_dir must be provided for the first step")
            self._context = {
                "startup_dir": startup_dir,
                "namespace": ns,
            }
        elif startup_dir is not None or ns is not None:
            if startup_dir is not None:
                self._context["startup_dir"] = startup_dir
            if ns is not None:
                self._context["namespace"] = ns

        step = self.steps[idx]
        
        deps_satisfied, missing_deps = self._check_dependencies(step)
        if not deps_satisfied:
            missing_names = [dep.__name__ for dep in missing_deps]
            raise RuntimeError(
                f"Step '{step.name}' cannot run: missing dependencies: {missing_names}"
            )

        print(f"Beamline Initialization Step {idx + 1}/{len(self.steps)}: {step.name}")

        try:
            self._context = step.execute(self.beamline, self._context)
            self._completed_steps.add(idx)
            self._completed_step_classes.add(type(step))
            return step.name, self._context
        except Exception as e:
            raise RuntimeError(
                f"Initialization failed at step '{step.name}': {e}"
            ) from e

    def reset(self):
        """
        Reset the initialization state.

        Clears completed steps and context, allowing re-initialization.
        """
        self._completed_steps.clear()
        self._completed_step_classes.clear()
        self._context = {}
        self.beamline.reset()


    def initialize(
        self,
        startup_dir: str,
        ns: dict = None,
        num_steps: int = None,
        from_step: int = 0,
    ) -> BeamlineModel:
        """
        Execute the initialization pipeline.

        Parameters
        ----------
        startup_dir : str
            Directory containing configuration files
        ns : dict, optional
            Namespace for loading devices
        num_steps : int, optional
            Number of steps to execute. If None, executes all remaining steps.
        from_step : int, optional
            Index of the first step to execute (0-based). Default is 0.

        Returns
        -------
        BeamlineModel
            The beamline model (partially or fully initialized)

        Raises
        ------
        RuntimeError
            If any initialization step fails
        ValueError
            If from_step is out of range or num_steps is invalid
        """
        if from_step < 0 or from_step >= len(self.steps):
            raise ValueError(f"from_step must be between 0 and {len(self.steps) - 1}")

        if num_steps is not None and num_steps <= 0:
            raise ValueError("num_steps must be positive")

        if not self._context:
            self._context = {
                "startup_dir": startup_dir,
                "namespace": ns,
            }
        else:
            if startup_dir is not None:
                self._context["startup_dir"] = startup_dir
            if ns is not None:
                self._context["namespace"] = ns

        if from_step == 0 and not self._completed_steps:
            print(f"Initializing beamline from {startup_dir}")
        else:
            print(f"Continuing initialization from step {from_step + 1}")

        end_step = len(self.steps)
        if num_steps is not None:
            end_step = min(from_step + num_steps, len(self.steps))

        for idx in range(from_step, end_step):
            if idx in self._completed_steps:
                print(f"Beamline Initialization Step {idx + 1}/{len(self.steps)}: {self.steps[idx].name} (already completed)")
                continue

            step = self.steps[idx]
            deps_satisfied, missing_deps = self._check_dependencies(step)
            
            if not deps_satisfied:
                missing_names = [dep.__name__ for dep in missing_deps]
                print(
                    f"Beamline Initialization Step {idx + 1}/{len(self.steps)}: {step.name} "
                    f"(skipped - missing dependencies: {missing_names})"
                )
                continue

            print(f"Beamline Initialization Step {idx + 1}/{len(self.steps)}: {step.name}")

            try:
                self._context = step.execute(self.beamline, self._context)
                self._completed_steps.add(idx)
                self._completed_step_classes.add(type(step))
            except Exception as e:
                raise RuntimeError(
                    f"Initialization failed at step '{step.name}': {e}"
                ) from e

        if end_step == len(self.steps) and len(self._completed_steps) == len(self.steps):
            print("Beamline initialization complete")
        else:
            remaining = len(self.steps) - len(self._completed_steps)
            print(f"Beamline initialization paused: {remaining} step(s) remaining")

        return self.beamline
