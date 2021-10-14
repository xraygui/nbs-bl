import asyncio


async def generic_cmd(msg):
    command, obj, args, kwargs, _ = msg
    ret = getattr(obj, command)(*args, **kwargs)
    return ret
