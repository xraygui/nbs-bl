import json
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

    def __init__(self, *, dict_name, default=None, **kwargs):
        super().__init__(**kwargs)
        self._dict_name = dict_name
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

def RedisDevice(prefix, name="", keys=None, status_provider=None, **kwargs):
    """
    Factory function to create a Redis-backed Device with one Component per key.
    """
    keys = keys or {}

    attrs = {
        "_keys_config": keys,
        "_dict_name": prefix,
        "_status_provider": status_provider or _RedisSignal.default_status_provider,
    }
    for key, default in keys.items():
        attrs[key] = Cpt(_RedisSignal, name=key, dict_name=prefix, default=default)

    cls = type(f"RedisDevice_{name}", (Device,), attrs)
    obj = cls(prefix="", name=name, **kwargs)


    return obj

