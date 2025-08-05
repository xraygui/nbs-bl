import asyncio
from bluesky import RunEngine
from .beamline import GLOBAL_BEAMLINE
from bluesky_queueserver import is_re_worker_active
from .planStatus import GLOBAL_PLAN_STATUS


async def generic_cmd(msg):
    """
    Generic command handler for all commands
    """
    command, obj, args, kwargs, _ = msg
    ret = getattr(obj, command)(*args, **kwargs)
    return ret


async def call_obj(msg):
    """
    Call an object's method
    """
    obj = msg.obj
    kwargs = msg.kwargs
    args = msg.args
    command = kwargs.pop("method")
    ret = getattr(obj, command)(*args, **kwargs)
    return ret


async def _update_plan_status(msg):
    """
    Update the plan status
    """
    command, obj, args, kwargs, _ = msg
    GLOBAL_PLAN_STATUS["status"] = args[0]


async def _clear_plan_status(msg):
    """
    Clear the plan status
    """
    command, obj, args, kwargs, _ = msg
    GLOBAL_PLAN_STATUS["status"] = "idle"


def load_RE_commands(engine):
    engine.register_command("call_obj", call_obj)
    engine.register_command("update_plan_status", _update_plan_status)
    engine.register_command("clear_plan_status", _clear_plan_status)


def setup_run_engine(RE):
    load_RE_commands(RE)
    RE.preprocessors.append(GLOBAL_BEAMLINE.supplemental_data)
    return RE


def create_run_engine(setup=True):
    if is_re_worker_active():
        RE = RunEngine(call_returns_result=False)
    else:
        RE = RunEngine(call_returns_result=True)
    if setup:
        setup_run_engine(RE)
    return RE
