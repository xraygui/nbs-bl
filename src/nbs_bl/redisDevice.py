import time
from collections import OrderedDict
from ophyd.signal import Signal
from ophyd.device import Device, Component as Cpt



class _RedisSignal(Signal):
    """
    Minimal signal-like wrapper around a Redis-backed USER_STATUS entry.

    Parameters
    ----------
    dict_name : str
        Name of the USER_STATUS dictionary to access.
    key : str
        Key within the dictionary.
    default : any
        Default value to use if key is missing.
    """
    default_status_provider = None

    @classmethod
    def set_default_status_provider(cls, provider):
        cls.default_status_provider = provider

    def __init__(self, *, dict_name=None, default=None, **kwargs):
        super().__init__(**kwargs)
        parent_prefix = getattr(self.parent, "prefix", None)
        resolved_dict = dict_name or parent_prefix
        if not resolved_dict:
            raise ValueError("RedisSignal requires a dict_name or parent prefix")
        self._dict_name = resolved_dict
        self._key = self.name
        self._default = default
        provider = self._status_provider()
        if self._dict_name not in provider:
            provider.request_status_dict(self._dict_name, use_redis=True)
        self._ensure_key_exists()

    def _ensure_key_exists(self):
        dct = self._status_provider()[self._dict_name]
        if self._key not in dct:
            dct[self._key] = self._default

    def get(self, **kwargs):
        try:
            dct = self._status_provider()[self._dict_name]
            return dct.get(self._key, self._default)
        except Exception as e:
            print(f"RedisSignal get error for {self._dict_name}:{self._key}: {e}")
            return self._default

    def put(self, value, **kwargs):
        try:
            dct = self._status_provider()[self._dict_name]
            dct[self._key] = value
            # Notify subscribers
            self._run_subs(sub_type=self.SUB_VALUE, value=value, **kwargs)
            return value
        except Exception as e:
            print(f"RedisSignal put error for {self._dict_name}:{self._key}: {e}")
            return self._default

    def _status_provider(self):
        provider = getattr(self, "_provider", None) or _RedisSignal.default_status_provider
        if provider is None:
            raise RuntimeError("No status provider configured for RedisDevice")
        return provider


class _RedisStatusListSignal(Signal):
    """
    Signal interface for a status list managed by GLOBAL_USER_STATUS.

    Parameters
    ----------
    status_key : str
        Status manager key for the list.
    default : iterable, optional
        Default values to use when the status list is empty.
    dtype : str, optional
        Event-model dtype to advertise for list elements.
    """

    def __init__(
        self,
        *,
        status_key,
        default=None,
        dtype="string",
        use_redis=True,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._status_key = status_key
        self._default = list(default or [])
        self._dtype = dtype
        self._use_redis = use_redis

    def get(self, **kwargs):
        try:
            return self._get_values()
        except Exception as e:
            print(f"RedisStatusListSignal get error for {self._status_key}: {e}")
            return list(self._default)

    def put(self, value, **kwargs):
        try:
            values = self._coerce_values(value)
            self._set_values(values)
            self._run_subs(sub_type=self.SUB_VALUE, value=values, **kwargs)
            return values
        except Exception as e:
            print(f"RedisStatusListSignal put error for {self._status_key}: {e}")
            return self.get()

    def read(self):
        return OrderedDict(
            [
                (
                    self.name,
                    {
                        "value": self.get(),
                        "timestamp": time.time(),
                    },
                )
            ]
        )

    def describe(self):
        try:
            shape = [len(self._get_values())]
        except Exception:
            shape = [len(self._default)]
        return OrderedDict(
            [
                (
                    self.name,
                    {
                        "source": getattr(self, "source", f"SIM:{self.name}"),
                        "dtype": self._dtype,
                        "shape": shape,
                    },
                )
            ]
        )

    def _get_values(self):
        provider = self._status_provider()
        values = provider.request_status_list(self._status_key, use_redis=self._use_redis)
        if not values and self._default:
            values = provider.set_status_list(
                self._status_key,
                self._default,
                use_redis=self._use_redis,
            )
        return list(values)

    def _set_values(self, values):
        provider = self._status_provider()
        provider.set_status_list(
            self._status_key,
            values,
            use_redis=self._use_redis,
        )

    def _coerce_values(self, value):
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        try:
            return list(value)
        except TypeError:
            return [value]

    def _status_provider(self):
        parent = getattr(self, "parent", None)
        provider = getattr(parent, "_status_provider", None)
        provider = provider or _RedisSignal.default_status_provider
        if provider is None:
            raise RuntimeError("No status provider configured for RedisModeDevice")
        return provider


def RedisDevice(prefix, name="", keys=None, status_provider=None, **kwargs):
    """
    Factory function to create a Redis-backed Device with one Component per key.
    """
    keys = keys or {}

    attrs = {
        "_keys_config": keys,
        "_dict_name": None,
        "_status_provider": status_provider or _RedisSignal.default_status_provider,
    }
    for key, default in keys.items():
        attrs[key] = Cpt(_RedisSignal, name=key, default=default)

    cls = type(f"RedisDevice_{name}", (Device,), attrs)
    obj = cls(prefix=prefix, name=name, **kwargs)


    return obj

class RedisModeDevice(Device):

    active_modes = Cpt(
        _RedisStatusListSignal,
        name="active_modes",
        status_key="ACTIVE_MODES",
        default=["default"],
    )

    def __init__(self, prefix, name="", status_provider=None, **kwargs):
        super().__init__(prefix=prefix, name=name, **kwargs)
        self._status_provider = status_provider or _RedisSignal.default_status_provider

    def get_active_modes(self):
        """
        Return active modes as a Python list.

        Returns
        -------
        list of str
            Active modes from the shared status list.
        """
        return self.active_modes._get_values()

    def set_active_modes(self, modes):
        """
        Update the readable mode signals from the beamline state.

        Parameters
        ----------
        modes : iterable of str
            Active modes to expose through this device.
        """
        self.active_modes.put(modes)
