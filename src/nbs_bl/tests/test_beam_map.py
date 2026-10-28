from pathlib import Path

import pytest
from ophyd import Device
from ophyd.sim import make_fake_device

from nbs_bl.beam_map import BeamMap, BeamMapFactory, MapNode, beam_map_class, read_map_file

EXAMPLE = str(Path(__file__).parent / "beam_map_example.toml")


def write_map(tmp_path, text):
    path = tmp_path / "map.toml"
    path.write_text(text)
    return str(path)


def fake_map(endstation="branch1", prefix=None):
    """A BeamMap whose status signals are ophyd fakes, all reading beam expected."""
    spec = read_map_file(EXAMPLE)
    cls = make_fake_device(beam_map_class(spec))
    bmap = cls(spec["prefix"] if prefix is None else prefix, name="beam_map",
               map_spec=spec, endstation=endstation)
    for node in bmap.nodes.values():
        node.path_clear.sim_put(1)
        node.beam_expected.sim_put(1)
        node.reason.sim_put("")
    return bmap


def real_map(prefix=None):
    """A BeamMap with real (unconnected) EPICS signals, for PV names."""
    spec = read_map_file(EXAMPLE)
    return beam_map_class(spec)(spec["prefix"] if prefix is None else prefix,
                                name="beam_map", map_spec=spec)


def test_is_an_ophyd_device_tree():
    bmap = fake_map()
    assert isinstance(bmap, BeamMap) and isinstance(bmap, Device)
    assert isinstance(bmap.nodes["m1"], MapNode)
    assert bmap.map_name == "claude"
    assert bmap.roots() == ["front_end"]
    assert bmap.nodes["m1"].children == ["branch1", "branch2"]
    assert bmap.nodes["branch1"].upstream == "m1"
    assert bmap.nodes["front_end"].desc == "Front-end shutter"


def test_signal_names():
    node = real_map().nodes["branch2"]
    assert node.blocking.pvname == "NBS_MAP:branch2:Blocking"
    assert node.path_clear.pvname == "NBS_MAP:branch2:PathClear"
    assert node.beam_expected.pvname == "NBS_MAP:branch2:BeamExpected"
    assert node.reason.pvname == "NBS_MAP:branch2:Reason"


def test_prefix_override():
    assert real_map(prefix="OTHER:").nodes["m1"].reason.pvname == "OTHER:m1:Reason"


def test_node_names_that_are_not_identifiers(tmp_path):
    spec = read_map_file(write_map(tmp_path, '[nodes.front-end]\n[nodes."m1 mirror"]\nupstream = "front-end"\n'))
    bmap = beam_map_class(spec)("P:", name="bm", map_spec=spec)
    assert bmap.nodes["m1 mirror"].reason.pvname == "P:m1 mirror:Reason"
    assert bmap.nodes["front-end"].children == ["m1 mirror"]


def test_ignores_conditions():
    bmap = real_map()
    names = {
        sig.pvname
        for node in bmap.nodes.values()
        for sig in (node.blocking, node.path_clear, node.beam_expected, node.reason)
    }
    assert all(name.startswith("NBS_MAP:") for name in names)
    assert len(names) == 16


def test_rejects_cycle(tmp_path):
    path = write_map(tmp_path, '[nodes.a]\nupstream = "b"\n[nodes.b]\nupstream = "a"\n')
    with pytest.raises(ValueError, match="cycle"):
        read_map_file(path)


def test_rejects_unknown_upstream(tmp_path):
    with pytest.raises(ValueError, match="nope"):
        read_map_file(write_map(tmp_path, '[nodes.a]\nupstream = "nope"\n'))


def test_beam_expected_for_endstation():
    bmap = fake_map()
    assert bmap.endstation == "branch1"
    assert bmap.beam_expected() is True
    assert bmap.why_no_beam() == ""
    bmap.nodes["branch1"].beam_expected.sim_put(0)
    bmap.nodes["branch1"].reason.sim_put("front_end blocked: X = 1")
    assert bmap.beam_expected() is False
    assert bmap.why_no_beam() == "front_end blocked: X = 1"
    assert bmap.beam_status() == {
        "endstation": "branch1",
        "beam_expected": False,
        "reason": "front_end blocked: X = 1",
    }


def test_status_functions_take_any_node():
    bmap = fake_map()
    bmap.nodes["branch2"].beam_expected.sim_put(0)
    assert bmap.beam_expected("branch2") is False
    assert bmap.beam_expected() is True


def test_unknown_endstation_is_ignored():
    bmap = fake_map(endstation="nope")
    assert bmap.endstation is None
    with pytest.raises(ValueError, match="endstation"):
        bmap.beam_expected()


def test_publish_tree_and_live_status():
    bmap = fake_map()
    out = {}
    bmap.publish(out)
    assert out["endstation"] == "branch1"
    assert out["beam_expected"] is True
    m1 = out["nodes"]["m1"]
    assert m1["upstream"] == "front_end"
    assert m1["children"] == ["branch1", "branch2"]
    assert m1["beam_expected"] is True
    bmap.nodes["branch1"].beam_expected.sim_put(0)
    bmap.nodes["branch1"].reason.sim_put("branch1 not selected: X = 0")
    assert out["nodes"]["branch1"]["beam_expected"] is False
    assert out["beam_expected"] is False
    assert out["reason"] == "branch1 not selected: X = 0"


def test_factory_resolves_map_file_from_startup_dir(tmp_path, monkeypatch):
    from nbs_bl.beamline import GLOBAL_BEAMLINE

    (tmp_path / "beam_map.toml").write_text(Path(EXAMPLE).read_text())
    monkeypatch.setitem(GLOBAL_BEAMLINE.settings, "startup_dir", str(tmp_path))
    bmap = BeamMapFactory("beam_map.toml", name="beam_map", endstation="branch2")
    assert isinstance(bmap, BeamMap)
    assert bmap.name == "beam_map"
    assert bmap.endstation == "branch2"
    assert bmap.nodes["m1"].reason.pvname == "NBS_MAP:m1:Reason"
    assert BeamMapFactory(EXAMPLE, name="bm2").map_name == "claude"


class FakeBeamline:
    def __init__(self, bmap=None):
        self.settings = {}
        self.beam_map = bmap
        self.md = {}


def test_setup_step_sets_md_and_namespace():
    from nbs_bl.configuration import SetupBeamMapStep

    bl = FakeBeamline(fake_map(endstation="branch2"))
    ns = {}
    SetupBeamMapStep().execute(bl, {"startup_dir": ".", "namespace": ns})
    from nbs_bl.beam_map import beam_expected

    assert bl.md["endstation"] == "branch2"
    assert ns["beam_expected"] is beam_expected


def test_setup_step_without_a_map():
    from nbs_bl.configuration import SetupBeamMapStep

    bl = FakeBeamline()
    SetupBeamMapStep().execute(bl, {"startup_dir": ".", "namespace": {}})
    assert bl.md == {}


def test_beam_map_role_is_allowed():
    from nbs_bl.beamline import BeamlineModel

    assert "beam_map" not in BeamlineModel.reserved
    assert BeamlineModel().beam_map is None


DEVICE_CONFIG = {
    "fe": {"_target": "x.Shutter", "_node": "front_end", "prefix": "P:fe:"},
    "mirror": {"_target": "x.Mirror", "_node": "m1", "_defer_loading": True},
    "mirror_x": {"_alias": "mirror.x"},
    "mirror_y": {"_alias": "mirror.y", "_node": "branch2"},
    "det": {"_target": "x.Det", "_node": "branch1"},
    "lost": {"_target": "x.Det", "_node": "nowhere"},
    "loose": {"_target": "x.Det"},
    "beam_map": {"_target": "nbs_bl.beam_map.BeamMapFactory", "_role": "beam_map", "_node": "m1"},
}


def test_attach_devices_alias_inherits_root_node(capsys):
    bmap = fake_map()
    bmap.attach_devices(DEVICE_CONFIG)
    assert bmap.nodes["m1"].devices == ["mirror", "mirror_x"]
    assert bmap.nodes["branch2"].devices == ["mirror_y"]
    assert bmap.nodes["front_end"].devices == ["fe"]
    assert "lost" in capsys.readouterr().out
    assert bmap.node_of("lost") is None
    assert bmap.node_of("loose") is None
    assert bmap.node_of("beam_map") is None


def test_devices_at_and_node_of():
    bmap = fake_map(endstation="branch1")
    bmap.attach_devices(DEVICE_CONFIG)
    assert bmap.devices_at() == ["det"]
    assert bmap.devices_at("m1") == ["mirror", "mirror_x"]
    assert bmap.node_of("mirror_x") == "m1"
    assert bmap.node_of("nope") is None


def test_attach_devices_is_idempotent():
    bmap = fake_map()
    bmap.attach_devices(DEVICE_CONFIG)
    bmap.attach_devices(DEVICE_CONFIG)
    assert bmap.nodes["m1"].devices == ["mirror", "mirror_x"]
    bmap.attach_devices({"det": {"_node": "m1"}})
    assert bmap.nodes["m1"].devices == ["det"]
    assert bmap.nodes["front_end"].devices == []


def test_to_dict_lists_devices():
    bmap = fake_map()
    bmap.attach_devices(DEVICE_CONFIG)
    nodes = bmap.to_dict()["nodes"]
    assert nodes["m1"]["devices"] == ["mirror", "mirror_x"]
    assert nodes["branch1"]["devices"] == ["det"]


def test_module_helpers_use_global_map(monkeypatch):
    from nbs_bl import beam_map
    from nbs_bl.beamline import GLOBAL_BEAMLINE

    bmap = fake_map(endstation="branch1")
    bmap.attach_devices(DEVICE_CONFIG)
    monkeypatch.setattr(GLOBAL_BEAMLINE, "beam_map", bmap)
    assert beam_map.devices_at() == ["det"]
    assert beam_map.node_of("fe") == "front_end"


def test_setup_step_attaches_devices():
    from nbs_bl.configuration import SetupBeamMapStep
    from nbs_bl.beam_map import devices_at, node_of

    bl = FakeBeamline(fake_map(endstation="branch1"))
    bl.config = {"devices": DEVICE_CONFIG}
    ns = {}
    SetupBeamMapStep().execute(bl, {"startup_dir": ".", "namespace": ns})
    assert bl.beam_map.nodes["branch1"].devices == ["det"]
    assert ns["devices_at"] is devices_at
    assert ns["node_of"] is node_of


def test_suspender_watches_endstation_beam_expected(monkeypatch):
    import nbs_bl.beam_map as bm

    bmap = fake_map()
    monkeypatch.setattr(bm, "_current_map", lambda: bmap)
    (sus,) = bm.beam_map_suspender(sleep=1)
    assert sus._sig is bmap.nodes["branch1"].beam_expected
    assert bm.beam_map_suspender(sleep=1) == [sus]


def test_no_suspender_without_a_map(monkeypatch):
    import nbs_bl.beam_map as bm

    def no_map():
        raise RuntimeError("No beam map loaded")

    monkeypatch.setattr(bm, "_current_map", no_map)
    assert bm.beam_map_suspender() == []
