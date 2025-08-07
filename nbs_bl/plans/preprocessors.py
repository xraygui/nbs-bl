from bluesky.plan_stubs import open_run, close_run
from bluesky.utils import RunEngineControlException, make_decorator
from bluesky.preprocessors import contingency_wrapper
from bluesky.preprocessors import plan_mutator, ensure_generator, single_gen
from bluesky import Msg
from functools import wraps
from ..utils import merge_func
from copy import deepcopy
import inspect
import uuid
from typing import Optional


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
    def _inner(*args, md: Optional[dict] = None, plan_level=0, **kwargs):
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
        if "md" in arguments:
            del arguments["md"]

        _md["plan_history"] = []
        if plan_level == 0:
            _md["master_plan"] = plan_name
            _md["batch_uid"] = str(uuid.uuid4())
        _md.update(deepcopy(md))
        _md["plan_history"].append(
            {"plan_name": plan_name, "arguments": arguments, "plan_level": plan_level}
        )
        return plan_function(*args, md=_md, plan_level=plan_level + 1, **kwargs)

    return _inner


def wrap_metadata(param):
    def decorator(func):
        @merge_func(func)
        def inner(*args, md: Optional[dict] = None, **kwargs):
            md = md or {}
            _md = {}
            _md.update(param)
            _md.update(md)
            return (yield from func(*args, md=_md, **kwargs))

        return inner

    return decorator


def run_return_wrapper(plan, *, md: Optional[dict] = None):
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
            yield from close_run(exit_status="fail", reason=str(e))

    return (
        yield from contingency_wrapper(
            plan, except_plan=except_plan, else_plan=close_run
        )
    )


run_return_decorator = make_decorator(run_return_wrapper)


def plan_status_decorator(func):
    """
    Update plan status, and clear after plan completion

    Parameters
    ----------
    plan : iterable or iterator
        a generator, list, or similar containing `Msg` objects
    status : str
        the status to update to

    Yields
    ------
    msg : Msg
        messages from plan with 'update_plan_status', and 'clear_plan_status' messages inserted

    """

    @merge_func(func)
    def _inner(*args, md: Optional[dict] = None, **kwargs):
        # Get plan name from metadata if available
        md = md or {}
        plan_name = md.get("plan_name", func.__name__) if md else func.__name__
        status = "Running " + plan_name
        print(f"Plan status decorator: {status}")
        update_msgs = [Msg("update_plan_status", None, status)]
        clear_msgs = [Msg("clear_plan_status")]

        def insert_after_open(msg):
            if msg.command == "open_run":

                def new_gen():
                    yield from ensure_generator(update_msgs)

                return single_gen(msg), new_gen()
            else:
                return None, None

        def insert_before_close(msg):
            if msg.command == "close_run":

                def new_gen():
                    yield from ensure_generator(clear_msgs)
                    yield msg

                return new_gen(), None
            else:
                return None, None

        # Apply nested mutations.
        plan1 = plan_mutator(func(*args, md=md, **kwargs), insert_after_open)
        plan2 = plan_mutator(plan1, insert_before_close)
        return (yield from plan2)

    return _inner
