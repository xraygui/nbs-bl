from os.path import exists
from .globalVars import GLOBAL_SETTINGS

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

"""
Example Beamline Settings:
What we need to capture

[settings]
modules = ['ucal.startup']
regions = ['regions.toml']

[settings.redis]
host = "redis"
prefix = "nexafs-"

"""

_default_settings = {
    "device_filename": "devices.toml",
    "beamline_filename": "beamline.toml",
}


def load_settings(settings_file):
    """
    Load settings from a TOML file.

    Parameters
    ----------
    settings_file : str
        The path to the settings file.

    Returns
    -------
    dict
        The settings loaded from the file.
    """
    # Things that are currently in ucal configuration/settings
    settings_dict = {}
    settings_dict.update(_default_settings)
    if not exists(settings_file):
        print("No settings found, using defaults")
        config = {}
    else:
        with open(settings_file, "rb") as f:
            config = tomllib.load(f)
    settings_dict.update(config.get("settings", {}))
    GLOBAL_SETTINGS.update(settings_dict)


"""
    s BeamlineSettings:
    device_filename = "devices.toml"
    beamline_filename = "beamline.toml"
    beamline_prefix = "sst"
    modules = []

settings = BeamlineSettings()
"""
