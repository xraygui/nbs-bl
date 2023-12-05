from sst_funcs.printing import boxed_text

GLOBAL_HELP_DICTIONARY = {'functions': {}, 'plans': {}, 'scans': {}, 'xas': {}}
GLOBAL_IMPORT_DICTIONARY = {}


def add_to_func_list(f):
    """
    A function decorator that will add the function to the built-in list
    """
    key = f.__name__
    doc = f.__doc__ if f.__doc__ is not None else "No Docstring yet!"
    GLOBAL_HELP_DICTIONARY['functions'][key] = doc
    GLOBAL_IMPORT_DICTIONARY[key] = f
    return f


def add_to_plan_list(f):
    """
    A function decorator that will add the plan to the built-in list
    """
    key = f.__name__
    doc = f.__doc__ if f.__doc__ is not None else "No Docstring yet!"
    GLOBAL_HELP_DICTIONARY['plans'][key] = doc
    GLOBAL_IMPORT_DICTIONARY[key] = f
    return f


def add_to_scan_list(f):
    """
    A function decorator that will add the plan to the built-in list
    """
    key = f.__name__
    doc = f.__doc__ if f.__doc__ is not None else "No Docstring yet!"
    GLOBAL_HELP_DICTIONARY['scans'][key] = doc
    GLOBAL_IMPORT_DICTIONARY[key] = f
    return f

def add_to_xas_list(f):
    """
    A function decorator that will add the plan to the built-in list
    """
    key = f.__name__
    doc = f.__doc__ if f.__doc__ is not None else "No Docstring yet!"
    GLOBAL_HELP_DICTIONARY['xas'][key] = doc
    GLOBAL_IMPORT_DICTIONARY[key] = f
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
        if key == 'xas':
            for f in sorted(GLOBAL_HELP_DICTIONARY[key].keys()):
                doc = GLOBAL_IMPORT_DICTIONARY[f]._short_doc
                textList.append(f"{f}: {doc}")

        else:
            for f in sorted(GLOBAL_HELP_DICTIONARY[key].keys()):
                doc = GLOBAL_HELP_DICTIONARY[key][f].split('\n')[0]
                textList.append(f"{f}: {doc}")
        boxed_text(section, textList, "white")

@add_to_func_list
def beamline_help():
    print('Welcome to SST. For a list of loaded functions and plans, call print_builtins() \n' \
          'To print the docstring for any of the built-in functions, use the built-in python "?"'\
          ' command with the name of the desired function. \n I.e, typing activate_detector? will '\
          'print the help text for the "activate_detector" function')
        
