import asyncio


async def generic_cmd(msg):
    command, obj, args, kwargs, _ = msg
    ret = getattr(obj, command)(*args, **kwargs)
    return ret


async def call_obj(msg):
    obj = msg.obj
    kwargs = msg.kwargs
    args = msg.args
    command = kwargs.pop('method')
    ret = getattr(obj, command)(*args, **kwargs)
    return ret
