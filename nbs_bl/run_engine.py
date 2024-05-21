import asyncio
from bluesky import RunEngine
from .globalVars import GLOBAL_SUPPLEMENTAL_DATA
from bluesky_queueserver import is_re_worker_active


async def generic_cmd(msg):
    command, obj, args, kwargs, _ = msg
    ret = getattr(obj, command)(*args, **kwargs)
    return ret


async def call_obj(msg):
    obj = msg.obj
    kwargs = msg.kwargs
    args = msg.args
    command = kwargs.pop("method")
    ret = getattr(obj, command)(*args, **kwargs)
    return ret


def load_RE_commands(engine):
    engine.register_command("call_obj", call_obj)


def setup_run_engine(RE):
    load_RE_commands(RE)
    RE.preprocessors.append(GLOBAL_SUPPLEMENTAL_DATA)


def create_run_engine(setup=True):
    if is_re_worker_active():
        RE = RunEngine(call_returns_result=False)
    else:
        RE = RunEngine(call_returns_result=True)
    if setup:
        setup_run_engine(RE)
    return RE
