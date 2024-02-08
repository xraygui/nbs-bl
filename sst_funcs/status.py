import uuid
from abc import ABC, abstractmethod


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
    NORMAL_METHODS = ['__delitem__', '__setitem__', 'append', 'clear', 'extend',
                      'insert', 'pop', 'remove']
    REINIT_METHODS = ['__rmul__', '__iadd__', '__add__', '__imul__', '__mul__']


class StatusDict(StatusContainerBase, dict):
    NORMAL_METHODS = ['__delitem__', '__setitem__', 'clear', 'pop', 'update']
    REINIT_METHODS = ['__or__', '__ror__']


class StatusTuple(StatusContainerBase, tuple):
    NORMAL_METHODS = []
    REINIT_METHODS = ['__add__', '__mul__', '__rmul__']

    def __init__(self, *args, **kwargs):
        self._uid = uuid.uuid4()
        for method in self.NORMAL_METHODS:
            self.__class__._make_normal_method(method)

        for method in self.REINIT_METHODS:
            self.__class__._make_reinit_method(method)


class StatusSet(StatusContainerBase, set):
    NORMAL_METHODS = ['clear', 'pop', 'add', 'remove', 'update', 'discard',
                      'intersection_update',
                      'symmetric_difference_update']
    REINIT_METHODS = ['__and__', '__iand__', '__rand__', '__or__', '__ior__',
                      '__ixor__', '__xor__', '__ror__', '__rxor__',
                      'intersection', 'difference', 'union',
                      'symmetric_difference']
