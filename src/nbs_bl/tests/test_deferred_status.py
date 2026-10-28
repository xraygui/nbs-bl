import nbs_bl.queueserver as qs
from nbs_bl.queueserver import GlobalStatusManager
from nbs_bl.status import DeferredRedisStatusDict
from nbs_bl.plans.time_estimation import gscan_estimate


class FakeRedisDict(dict):
    """Stands in for RedisStatusDict; records the prefix it was made with."""

    def __init__(self, client, prefix=""):
        super().__init__()
        self.prefix = prefix


def test_deferred_dict_copies_and_writes_through():
    d = DeferredRedisStatusDict()
    d["a"] = {"x": 1}
    d["b"] = 2
    backing = FakeRedisDict(None)
    backing["stale"] = 0
    d.bind(backing)
    assert backing == {"a": {"x": 1}, "b": 2}
    d["c"] = 3
    d.update(e=5)
    d.pop("b")
    del d["a"]
    assert backing == {"c": 3, "e": 5} == dict(d)
    d.clear()
    assert backing == {}


def test_init_redis_binds_dicts_requested_earlier(monkeypatch):
    monkeypatch.setattr(qs, "open_redis_client_from_settings", lambda settings: object())
    monkeypatch.setattr(qs, "RedisStatusDict", FakeRedisDict)
    manager = GlobalStatusManager()
    early = manager.request_status_dict("PLAN_TIME_DICT", use_redis=True)
    early["c_xas"] = {"estimator": "gscan_estimate"}
    manager.init_redis({"host": "localhost", "prefix": "claude-"})
    early["n_xas"] = {"estimator": "gscan_estimate"}
    backing = early._redis
    assert backing.prefix == "claude-PLAN_TIME_DICT"
    assert set(backing) == {"c_xas", "n_xas"}
    # Requests after init get a Redis dict directly
    late = manager.request_status_dict("XAS_PLANS", use_redis=True)
    assert isinstance(late, FakeRedisDict)


def test_gscan_estimate_uses_default_dwell():
    est = {"fixed": 5, "overhead": 0.5, "dwell": "dwell", "default_dwell": 1.0, "region": [0, 1, 10]}
    assert gscan_estimate("p", {}, est) == 5 + 1.5 * 11
    assert gscan_estimate("p", {"dwell": 2}, est) == 5 + 2.5 * 11
    assert gscan_estimate("p", {"repeat": 2}, {**est, "reset": 3}) == 2 * (5 + 1.5 * 11) + 3
