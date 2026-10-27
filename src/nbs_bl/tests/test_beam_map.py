from pathlib import Path

import pytest

from nbs_bl.beam_map import load_beam_map

EXAMPLE = str(Path(__file__).parent / "beam_map_example.toml")


def write_map(tmp_path, text):
    path = tmp_path / "map.toml"
    path.write_text(text)
    return str(path)


def test_tree():
    bmap = load_beam_map(EXAMPLE)
    assert bmap.name == "claude"
    assert bmap.roots() == ["front_end"]
    assert bmap.nodes["m1"].children == ["branch1", "branch2"]
    assert bmap.nodes["branch1"].upstream == "m1"
    assert bmap.nodes["front_end"].desc == "Front-end shutter"


def test_signal_names():
    node = load_beam_map(EXAMPLE).nodes["branch2"]
    assert node.blocking.pvname == "NBS_MAP:branch2:Blocking"
    assert node.path_clear.pvname == "NBS_MAP:branch2:PathClear"
    assert node.beam_expected.pvname == "NBS_MAP:branch2:BeamExpected"
    assert node.reason.pvname == "NBS_MAP:branch2:Reason"


def test_prefix_override():
    bmap = load_beam_map(EXAMPLE, prefix="OTHER:")
    assert bmap.nodes["m1"].reason.pvname == "OTHER:m1:Reason"


def test_ignores_conditions():
    bmap = load_beam_map(EXAMPLE)
    names = {
        sig.pvname
        for node in bmap.nodes.values()
        for sig in (node.blocking, node.path_clear, node.beam_expected, node.reason)
    }
    assert all(name.startswith("NBS_MAP:") for name in names)
    assert len(names) == 16


def test_rejects_cycle(tmp_path):
    path = write_map(
        tmp_path, '[nodes.a]\nupstream = "b"\n[nodes.b]\nupstream = "a"\n'
    )
    with pytest.raises(ValueError, match="cycle"):
        load_beam_map(path)


def test_rejects_unknown_upstream(tmp_path):
    path = write_map(tmp_path, '[nodes.a]\nupstream = "nope"\n')
    with pytest.raises(ValueError, match="nope"):
        load_beam_map(path)


class FakeBeamline:
    def __init__(self):
        self.settings = {}
        self.beam_map = None


def test_startup_step_loads_map(tmp_path):
    from nbs_bl.configuration import LoadBeamMapStep

    (tmp_path / "beam_map.toml").write_text(Path(EXAMPLE).read_text())
    bl = FakeBeamline()
    LoadBeamMapStep().execute(bl, {"startup_dir": str(tmp_path)})
    assert list(bl.beam_map.nodes) == ["front_end", "m1", "branch1", "branch2"]


def test_startup_step_skips_missing_and_bad_maps(tmp_path):
    from nbs_bl.configuration import LoadBeamMapStep

    bl = FakeBeamline()
    LoadBeamMapStep().execute(bl, {"startup_dir": str(tmp_path)})
    assert bl.beam_map is None
    (tmp_path / "beam_map.toml").write_text('[nodes.a]\nupstream = "x"\n')
    LoadBeamMapStep().execute(bl, {"startup_dir": str(tmp_path)})
    assert bl.beam_map is None


def test_beamline_model_has_no_map_by_default():
    from nbs_bl.beamline import BeamlineModel

    assert BeamlineModel().beam_map is None
