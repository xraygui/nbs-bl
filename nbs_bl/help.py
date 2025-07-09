from .status import StatusList
from .queueserver import GLOBAL_USER_STATUS
from .printing import boxed_text

GLOBAL_HELP_DICTIONARY = {"functions": {}, "plans": {}, "scans": {}, "xas": {}}
GLOBAL_IMPORT_DICTIONARY = {}

# Request status lists from the global manager
GLOBAL_PLAN_LIST = GLOBAL_USER_STATUS.request_status_list("PLAN_LIST", use_redis=True)
GLOBAL_SCAN_LIST = GLOBAL_USER_STATUS.request_status_list("SCAN_LIST", use_redis=True)
GLOBAL_PLAN_TIME_DICT = GLOBAL_USER_STATUS.request_status_dict(
    "PLAN_TIME_DICT", use_redis=True
)


def _add_to_import_list(f, help_section):
    """
    A function decorator that will add the function to the built-in list
    """
    key = f.__name__
    doc = f.__doc__ if f.__doc__ is not None else "No Docstring yet!"
    if help_section not in GLOBAL_HELP_DICTIONARY:
        GLOBAL_HELP_DICTIONARY[help_section] = {}
    GLOBAL_HELP_DICTIONARY[help_section][key] = doc.lstrip()
    GLOBAL_IMPORT_DICTIONARY[key] = f
    return key


def add_to_func_list(f):
    """
    A function decorator that will add the function to the built-in list
    """
    _add_to_import_list(f, "functions")
    return f


def add_to_plan_list(f):
    """
    A function decorator that will add the plan to the built-in list
    """
    key = _add_to_import_list(f, "plans")
    GLOBAL_PLAN_LIST.append(key)
    return f


def add_to_scan_list(f):
    """
    A function decorator that will add the plan to the built-in list
    """
    key = _add_to_import_list(f, "scans")
    GLOBAL_SCAN_LIST.append(key)
    return f


def add_to_plan_time_dict(
    f,
    estimator="generic_estimate",
    fixed=0,
    overhead=0.5,
    dwell="dwell",
    points=None,
    reset=0,
):
    key = f.__name__
    if key not in GLOBAL_PLAN_TIME_DICT:
        GLOBAL_PLAN_TIME_DICT[key] = {}
    GLOBAL_PLAN_TIME_DICT[key]["estimator"] = estimator
    GLOBAL_PLAN_TIME_DICT[key]["fixed"] = fixed
    GLOBAL_PLAN_TIME_DICT[key]["overhead"] = overhead
    GLOBAL_PLAN_TIME_DICT[key]["dwell"] = dwell
    GLOBAL_PLAN_TIME_DICT[key]["points"] = points
    GLOBAL_PLAN_TIME_DICT[key]["reset"] = reset
    return f


@add_to_func_list
def print_builtins(sections=None):
    """Prints a list of built-in functions for ucal"""

    if sections is None:
        sections = sorted(GLOBAL_HELP_DICTIONARY.keys())
    if type(sections) is str:
        sections = [sections]
    for key in sections:
        textList = []
        section = f"{key.capitalize()}"
        if key == "xas":
            for f in sorted(GLOBAL_HELP_DICTIONARY[key].keys()):
                doc = GLOBAL_IMPORT_DICTIONARY[f]._short_doc
                textList.append(f"{f}: {doc}")

        else:
            for f in sorted(GLOBAL_HELP_DICTIONARY[key].keys()):
                doc = GLOBAL_HELP_DICTIONARY[key][f].split("\n")[0]
                textList.append(f"{f}: {doc}")
        boxed_text(section, textList, "white", width=100)


@add_to_func_list
def sst_help():
    print(
        "Welcome to SST. For a list of loaded functions and plans, call print_builtins() \n"
        'To print the docstring for any of the built-in functions, use the built-in python "?"'
        " command with the name of the desired function. \n I.e, typing activate_detector? will "
        'print the help text for the "activate_detector" function'
    )
