from sst_funcs.printing import boxed_text

GLOBAL_HELP_DICTIONARY = {'functions': {}, 'plans': {}, 'scans': {}}


def add_to_func_list(f):
    """
    A function decorator that will add the function to the built-in list
    """
    key = f.__name__
    doc = f.__doc__
    GLOBAL_HELP_DICTIONARY['functions'][key] = doc
    return f


def add_to_plan_list(f):
    """
    A function decorator that will add the plan to the built-in list
    """
    key = f.__name__
    doc = f.__doc__
    GLOBAL_HELP_DICTIONARY['plans'][key] = doc
    return f


def add_to_scan_list(f):
    """
    A function decorator that will add the plan to the built-in list
    """
    key = f.__name__
    doc = f.__doc__
    GLOBAL_HELP_DICTIONARY['scans'][key] = doc
    return f


@add_to_func_list
def print_builtins(sections=None):
    """Prints a list of built-in functions for ucal"""

    if sections is None:
        sections = sorted(GLOBAL_HELP_DICTIONARY.keys())
    if type(sections) is str:
        sections = [sections]
    for key in sections:
        section = f"{key.capitalize()}"
        boxed_text(section, sorted(GLOBAL_HELP_DICTIONARY[key].keys()), "white")
