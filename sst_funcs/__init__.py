from importlib.metadata import version, PackageNotFoundError
from os.path import join, exists
from .configuration import loadDeviceConfig
from . import hw

try:
    __version__ = version("sst_funcs")
except PackageNotFoundError:
    # package is not installed
    pass



# ip.user_ns['RE'] = RE
