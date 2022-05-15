from functools import wraps
import inspect


def sanitize(arg):
    # storable_types = (int, float, str, bool)
    if type(arg) == list:
        _arg = []
        for thing in arg:
            try:
                _arg.append(thing.name)
            except Exception:
                _arg.append(thing)
        return _arg
    else:
        if hasattr(arg, "name"):
            return arg.name
        else:
            return arg


def store_plan_md(plan_function):
    @wraps(plan_function)
    def _inner(*args, md=None, plan_level=0, **kwargs):
        plan_name = plan_function.__name__
        md = md or {}
        _md = {}
        arguments = {}
        s = inspect.signature(plan_function)
        for p in s.parameters.values():
            if p.default is not s.empty:
                arguments[p.name] = p.default

        for a, n in zip(args, plan_function.__code__.co_varnames):
            arguments[n] = sanitize(a)
        for k, v in kwargs.items():
            arguments[k] = sanitize(v)
        if 'md' in arguments:
            del arguments['md']

        _md['plan_history'] = []
        _md['master_plan'] = plan_name
        _md.update(md)
        _md['plan_history'].append({"plan_name": plan_name,
                                    "arguments": arguments,
                                    "plan_level": plan_level})
        return plan_function(*args, md=_md, plan_level=plan_level+1, **kwargs)
    return _inner
