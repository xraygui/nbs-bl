import uuid
from abc import ABC, abstractmethod
from redis_json_dict import RedisJSONDict


class StatusContainerBase(ABC):

    @classmethod
    @property
    @abstractmethod
    def NORMAL_METHODS(cls):
        raise NotImplementedError

    @classmethod
    @property
    @abstractmethod
    def REINIT_METHODS(cls):
        raise NotImplementedError

    @classmethod
    def _make_normal_method(cls, method):
        def _inner(self, *args):
            self._uid = uuid.uuid4()
            return getattr(super(), method)(*args)

        _inner.__name__ = method
        setattr(cls, method, _inner)

    @classmethod
    def _make_reinit_method(cls, method):
        def _inner(self, *args):
            self._uid = uuid.uuid4()
            newitem = getattr(super(), method)(*args)
            return self.__class__(newitem)

        _inner.__name__ = method
        setattr(cls, method, _inner)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._uid = uuid.uuid4()
        for method in self.NORMAL_METHODS:
            self.__class__._make_normal_method(method)

        for method in self.REINIT_METHODS:
            self.__class__._make_reinit_method(method)

    def get_uid(self):
        return self._uid


class StatusList(StatusContainerBase, list):
    NORMAL_METHODS = [
        "__delitem__",
        "__setitem__",
        "append",
        "clear",
        "extend",
        "insert",
        "pop",
        "remove",
    ]
    REINIT_METHODS = ["__rmul__", "__iadd__", "__add__", "__imul__", "__mul__"]


class StatusDict(StatusContainerBase, dict):
    NORMAL_METHODS = ["__delitem__", "__setitem__", "clear", "pop", "update"]
    REINIT_METHODS = ["__or__", "__ror__"]


class StatusTuple(StatusContainerBase, tuple):
    NORMAL_METHODS = []
    REINIT_METHODS = ["__add__", "__mul__", "__rmul__"]

    def __init__(self, *args, **kwargs):
        self._uid = uuid.uuid4()
        for method in self.NORMAL_METHODS:
            self.__class__._make_normal_method(method)

        for method in self.REINIT_METHODS:
            self.__class__._make_reinit_method(method)


class StatusSet(StatusContainerBase, set):
    NORMAL_METHODS = [
        "clear",
        "pop",
        "add",
        "remove",
        "update",
        "discard",
        "intersection_update",
        "symmetric_difference_update",
    ]
    REINIT_METHODS = [
        "__and__",
        "__iand__",
        "__rand__",
        "__or__",
        "__ior__",
        "__ixor__",
        "__xor__",
        "__ror__",
        "__rxor__",
        "intersection",
        "difference",
        "union",
        "symmetric_difference",
    ]


class DeferredRedisStatusDict(StatusDict):
    """
    A StatusDict that was asked to live in Redis before Redis was set up.

    It works as a plain dict until ``bind`` is called with a RedisStatusDict,
    then copies its contents there and writes every later top-level change
    through. Change whole values (``d[key] = {...}``), not nested items in
    place, or the Redis copy goes stale.
    """

    NORMAL_METHODS = []
    REINIT_METHODS = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._redis = None

    def bind(self, redis_dict):
        """Replace the contents of ``redis_dict`` with ours and keep it in sync."""
        redis_dict.clear()
        for key, value in dict.items(self):
            redis_dict[key] = value
        self._redis = redis_dict

    @property
    def bound(self):
        return self._redis is not None

    def __setitem__(self, key, value):
        self._uid = uuid.uuid4()
        dict.__setitem__(self, key, value)
        if self._redis is not None:
            self._redis[key] = value

    def __delitem__(self, key):
        self._uid = uuid.uuid4()
        dict.__delitem__(self, key)
        if self._redis is not None:
            del self._redis[key]

    def clear(self):
        self._uid = uuid.uuid4()
        dict.clear(self)
        if self._redis is not None:
            self._redis.clear()

    def pop(self, key, *default):
        present = key in self
        value = dict.pop(self, key, *default)
        if present:
            self._uid = uuid.uuid4()
            if self._redis is not None:
                del self._redis[key]
        return value

    def update(self, *args, **kwargs):
        for key, value in dict(*args, **kwargs).items():
            self[key] = value

    def setdefault(self, key, default=None):
        if key not in self:
            self[key] = default
        return dict.__getitem__(self, key)


class RedisStatusDict(StatusContainerBase, RedisJSONDict):
    NORMAL_METHODS = ["__delitem__", "__setitem__", "clear", "pop", "update"]
    REINIT_METHODS = []
