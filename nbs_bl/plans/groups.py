import uuid
from functools import wraps
from bluesky.preprocessors import inject_md_wrapper
from .preprocessors import wrap_metadata, merge_func


def repeat(func):
    @merge_func(func)
    def inner(*args, repeat: int = 1, **kwargs):
        if repeat > 1:
            repeat_uid = str(uuid.uuid4())
            return_list = []
            for i in range(repeat):
                repeat_md = {"repeat": {"uid": repeat_uid, "len": repeat, "index": i}}
                r = yield from wrap_metadata(repeat_md)(func)(*args, **kwargs)
                return_list.append(r)
            return return_list
        else:
            return (yield from func(*args, **kwargs))

    return inner


def group(groupname):
    def decorator(func):
        @merge_func(func)
        def inner(*args, **kwargs):
            md = {"group_md": {"uid": str(uuid.uuid4()), "name": groupname}}
            return (yield from inject_md_wrapper(func(*args, **kwargs), md))

        return inner

    return decorator


def simple_1d_sequence_factory(length, label, device=None):
    sq = {"shape": length, "label": label, "uid": str(uuid.uuid4())}
    if device is not None:
        sq["device_name"] = device.name
    index = iter(range(length))

    def add_to_sequence(plan, value):
        return (
            yield from inject_md_wrapper(
                plan, {"sequence": {**sq, "index": next(index), "value": value}}
            )
        )

    return add_to_sequence
