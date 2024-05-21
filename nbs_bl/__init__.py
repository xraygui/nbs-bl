"""
Why do I have anything at all in __init__?
from importlib.metadata import version, PackageNotFoundError
from os.path import join, exists
from .configuration import loadDeviceConfig

try:
    __version__ = version("sst_funcs")
except PackageNotFoundError:
    # package is not installed
    pass


"""
# ip.user_ns['RE'] = RE
