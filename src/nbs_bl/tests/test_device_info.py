import json

from bluesky.preprocessors import SupplementalData
from ophyd.sim import SynAxis, motor

from nbs_bl.device_info import device_info
from nbs_bl.tests.test_beam_map import fake_map

PREFIX = "XF:99ID-TEST{Dev:1}"

CONFIG = {
    "slit": {
        "_target": "ophyd.sim.SynAxis",
        "_group": "motors",
        "_node": "m1",
        "_role": "slits",
        "_desc": "Exit slit.",
        "_axes": {"x": {"dir": "x", "desc": "across"}},
        "prefix": PREFIX,
        "name": "slit",
        "delay": 0.5,
    },
    "slit_sp": {"_alias": "slit.setpoint", "_group": "motors"},
    "late": {
        "_target": "some.module.LateDetector",
        "_group": ["detectors", "misc"],
        "_node": "branch1",
        "_defer_loading": True,
        "_sample_frame": {"x": "horizontal"},
        "prefix": PREFIX + "late:",
    },
    "stray": {"_target": "some.module.Thing", "_node": "nowhere", "prefix": PREFIX},
}


class FakeBeamline:
    def __init__(self, with_map=True):
        self.slit = SynAxis(name="slit")
        self.config = {"devices": CONFIG}
        self.devices = {"slit": self.slit, "slit_sp": self.slit.setpoint, "extra": motor}
        self._deferred_devices = {"late"}
        self.supplemental_data = SupplementalData(baseline=[self.slit])
        self.beam_map = None
        if with_map:
            self.beam_map = fake_map()
            self.beam_map.attach_devices(CONFIG)


def test_loaded_device_fields():
    info = device_info("slit", beamline=FakeBeamline())["slit"]
    assert info == {
        "class": "SynAxis",
        "node": "m1",
        "groups": ["motors"],
        "roles": ["slits"],
        "desc": "Exit slit.",
        "axes": {"x": {"dir": "x", "desc": "across"}},
        "loaded": True,
        "in_baseline": True,
        "components": list(SynAxis(name="s").component_names),
    }


def test_alias_inherits_node():
    info = device_info(["slit_sp"], beamline=FakeBeamline())["slit_sp"]
    assert info["alias_of"] == "slit.setpoint"
    assert info["node"] == "m1"
    assert info["loaded"] is True
    assert info["groups"] == ["motors"]
    assert "in_baseline" not in info


def test_deferred_device():
    info = device_info("late", beamline=FakeBeamline())["late"]
    assert info["class"] == "LateDetector"
    assert info["deferred"] is True
    assert info["loaded"] is False
    assert info["node"] == "branch1"
    assert info["groups"] == ["detectors", "misc"]
    assert info["sample_frame"] == {"x": "horizontal"}
    assert "components" not in info


def test_node_falls_back_to_config_without_a_map():
    bl = FakeBeamline(with_map=False)
    assert device_info("slit", beamline=bl)["slit"]["node"] == "m1"
    assert device_info("slit_sp", beamline=bl)["slit_sp"].get("node") is None


def test_unknown_and_all():
    bl = FakeBeamline()
    assert device_info("nope", beamline=bl) == {"nope": {"error": "unknown device"}}
    everything = device_info(beamline=bl)
    assert list(everything) == ["slit", "slit_sp", "late", "stray", "extra"]
    assert everything["stray"]["node"] == "nowhere"
    assert everything["extra"]["class"] == "SynAxis"


def test_no_prefix_or_constructor_kwargs():
    text = json.dumps(device_info(beamline=FakeBeamline()))
    assert PREFIX not in text
    assert "XF:" not in text
    assert "delay" not in text
    assert "_defer_loading" not in text


def test_setup_step_adds_function_to_namespace():
    from nbs_bl.configuration import SetupDeviceInfoStep

    ns = {}
    SetupDeviceInfoStep().execute(FakeBeamline(), {"namespace": ns})
    assert ns["device_info"] is device_info
