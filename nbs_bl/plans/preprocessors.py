from bluesky.plan_stubs import open_run, close_run
from bluesky.utils import RunEngineControlException, make_decorator
from bluesky.preprocessors import contingency_wrapper
from functools import wraps
from ..utils import merge_func
from copy import deepcopy
import inspect
import uuid


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


def plan_md_decorator(plan_function):
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
        if plan_level == 0:
            _md['master_plan'] = plan_name
            _md['batch_uid'] = str(uuid.uuid4())
        _md.update(deepcopy(md))
        _md['plan_history'].append({"plan_name": plan_name,
                                    "arguments": arguments,
                                    "plan_level": plan_level})
        return plan_function(*args, md=_md, plan_level=plan_level+1, **kwargs)
    return _inner


def wrap_metadata(param):
    def decorator(func):
        @merge_func(func)
        def inner(*args, md=None, **kwargs):
            md = md or {}
            _md = {}
            _md.update(param)
            _md.update(md)
            return (yield from func(*args, md=_md, **kwargs))
        return inner
    return decorator


def run_return_wrapper(plan, *, md=None):
    """Enclose in 'open_run' and 'close_run' messages.

    Parameters
    ----------
    plan : iterable or iterator
        a generator, list, or similar containing `Msg` objects
    md : dict, optional
        metadata to be passed into the 'open_run' message
    """
    yield from open_run(md)

    def except_plan(e):
        if isinstance(e, RunEngineControlException):
            yield from close_run(exit_status=e.exit_status)
        else:
            yield from close_run(exit_status='fail', reason=str(e))

    return (yield from contingency_wrapper(plan,
                                           except_plan=except_plan,
                                           else_plan=close_run))


run_return_decorator = make_decorator(run_return_wrapper)
