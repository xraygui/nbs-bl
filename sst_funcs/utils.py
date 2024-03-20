import collections
import inspect
from functools import update_wrapper
from numpydoc.docscrape import NumpyDocString, Parameter
import copy


def iterfy(x):
    """
    This function guarantees that a parameter passed will act like a list (or tuple) for the purposes of iteration,
    while treating a string as a single item in a list.

    Parameters
    ----------
    x : Any
        The input parameter to be iterfied.

    Returns
    -------
    Iterable
        The input parameter as an iterable.
    """
    if isinstance(x, collections.abc.Iterable) and not isinstance(x, (str, bytes)):
        return x
    else:
        return [x]


def adjust_signature(*omit_args):
    """
    A decorator factory that adjusts the signature of the decorated function.
    It omits specified arguments from the function's signature.

    Parameters
    ----------
    *omit_args : str
        Names of the arguments to be omitted from the function's signature.

    Returns
    -------
    function
        The decorated function with an adjusted signature.

    Example
    -------
    @adjust_signature('arg_to_omit')
    def func(arg_to_keep, arg_to_omit):
        pass
    """

    def decorator(func):
        sig = inspect.signature(func)
        new_params = [p for name, p in sig.parameters.items() if name not in omit_args]
        new_sig = sig.replace(parameters=new_params)
        func.__signature__ = new_sig
        return func

    return decorator


def merge_signatures(func):
    def decorator(wrapper):
        # Get the signatures of the two functions
        sig_func = inspect.signature(func)
        sig_wrapper = inspect.signature(wrapper)

        # Separate positional and keyword parameters from variadic keyword parameters
        func_params = list(sig_func.parameters.values())[1:]
        wrapper_params = [
            param
            for param in sig_wrapper.parameters.values()
            if param.kind != param.VAR_KEYWORD
        ]
        wrapper_var_keyword_params = [
            param
            for param in sig_wrapper.parameters.values()
            if param.kind == param.VAR_KEYWORD
        ]

        # Create a new parameters list that includes parameters from both functions

        new_params = (
            wrapper_params
            + [
                param
                for param in func_params
                if param.name not in sig_wrapper.parameters
            ]
            + wrapper_var_keyword_params
        )

        # Create a new signature with the combined parameters
        new_sig = sig_wrapper.replace(parameters=new_params)

        # Update the signature of the wrapper function
        wrapper.__signature__ = new_sig

        # Update the docstring and other attributes of the wrapper function
        update_wrapper(wrapper, func)

        return wrapper

    return decorator


def merge_docstrings(doc1, doc2, omit_params=[], param_order=None):
    """
    Merge two numpy-style docstrings.

    Parameters
    ----------
    doc1 : str
        The first docstring.
    doc2 : str
        The second docstring.
    omit_params : list of str
        The names of parameters to omit from the final function signature and docstring.

    Returns
    -------
    str
        The merged docstring.
    """
    # Parse the docstrings
    if doc1 is None:
        doc1 = ""
    if doc2 is None:
        doc2 = ""
    parsed_doc1 = NumpyDocString(doc1)
    parsed_doc2 = NumpyDocString(doc2)

    # Merge the parameters
    params1 = {name: (typ, desc) for name, typ, desc in parsed_doc1["Parameters"]}
    params2 = {name: (typ, desc) for name, typ, desc in parsed_doc2["Parameters"]}
    params1.update(params2)
    merged_params = [
        Parameter(name, *params1[name]) for name in params1 if name not in omit_params
    ]

    # Sort the parameters so that any parameter with a "**" in its name is placed at the end
    if param_order:
        merged_params.sort(
            key=lambda param: (
                (
                    param_order.index(param.name)
                    if param.name in param_order
                    else len(param_order)
                ),
                param.name,
            )
        )
    else:
        merged_params.sort(key=lambda param: "**" in param.name)

    # Create a copy of the first parsed docstring
    merged_doc = copy.deepcopy(parsed_doc1)

    # Update the 'Parameters' section of the copied docstring
    merged_doc["Parameters"] = merged_params

    # Convert the merged docstring back to a string
    return str(merged_doc)


def merge_func(
    func, omit_params=[], exclude_wrapper_args=True, exclude_wrapper_kwargs=True
):
    """
    A decorator that merges the docstrings and function signatures of the wrapped function and the wrapper function.

    Parameters
    ----------
    func : callable
        The function to be wrapped.
    omit_params : list of str
        The names of parameters to omit from the final function signature and docstring.

    Returns
    -------
    callable
        The wrapper function with the merged docstring and function signature.
    """

    def decorator(wrapper):
        # Merge the docstrings

        # Merge the function signatures
        sig_wrapper = inspect.signature(wrapper)
        sig_func = inspect.signature(func)

        # Get the parameters from the wrapper function and the wrapped function
        params_wrapper = list(sig_wrapper.parameters.values())
        if exclude_wrapper_args:
            params_wrapper = [
                param for param in params_wrapper if param.kind != param.VAR_POSITIONAL
            ]
        if exclude_wrapper_kwargs:
            params_wrapper = [
                param for param in params_wrapper if param.kind != param.VAR_KEYWORD
            ]
        params_func = [
            param
            for param in list(sig_func.parameters.values())
            if param.name not in sig_wrapper.parameters
        ]
        if params_func and params_func[0].name == "self":
            params_func = params_func[1:]

        combined_params = [
            param
            for param in params_wrapper + params_func
            if param.name not in omit_params
        ]
        combined_params.sort(key=lambda param: param.kind)
        param_order = [param.name for param in combined_params]
        merged_docstring = merge_docstrings(
            wrapper.__doc__, func.__doc__, omit_params, param_order
        )
        wrapper.__doc__ = merged_docstring
        # Create a new signature with the merged parameters
        new_sig = sig_wrapper.replace(parameters=combined_params)

        # Update the signature of the wrapper function
        wrapper.__signature__ = new_sig

        return wrapper

    return decorator
