from .status import StatusDict, StatusContainerBase
from collections import abc
from ophyd import OphydObject

GLOBAL_USER_STATUS = StatusDict()


def add_status(key, container: StatusContainerBase):
    GLOBAL_USER_STATUS[key] = container


def remove_status(key):
    del GLOBAL_USER_STATUS[key]


def get_status():
    status_dict = {k: str(v.get_uid()) for k, v in GLOBAL_USER_STATUS.items()}
    return status_dict


def request_update(key):
    if key in GLOBAL_USER_STATUS:
        sbuffer = GLOBAL_USER_STATUS[key]
        if isinstance(sbuffer, abc.Sequence):
            return represent_sequence(sbuffer)
        if isinstance(sbuffer, abc.Mapping):
            return represent_mapping(sbuffer)
        if isinstance(sbuffer, abc.Set):
            return represent_set(sbuffer)


def represent_item(item):
    if isinstance(item, OphydObject):
        return item.name
    elif isinstance(item, abc.Sequence):
        return represent_sequence(item)
    elif isinstance(item, abc.Mapping):
        return represent_mapping(item)
    elif isinstance(item, abc.Set):
        return represent_set(item)
    else:
        return item


def represent_mapping(m):
    rep = {}
    for k, v in m.items():
        rep[k] = represent_item(v)
    return rep


def represent_sequence(s):

    if isinstance(s, str):
        return s
    else:
        rep = []
        for v in s:
            rep.append(represent_item(v))
        return rep


def represent_set(s):
    return represent_sequence(s)


def print_mapping(m):
    return str(represent_mapping(m))


def print_sequence(s):
    return str(represent_sequence(s))


def print_set(s):
    return str(represent_set(s))
