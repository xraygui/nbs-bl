from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("sst_funcs")
except PackageNotFoundError:
    # package is not installed
    pass
