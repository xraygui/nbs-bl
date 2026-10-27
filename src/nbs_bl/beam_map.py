"""
Beamline map as ophyd devices, backed by the map IOC's status PVs.

The map file (e.g. ``beam_map.toml``) is shared with the map IOC in nbs-sim
(``nbs-map-ioc``), which watches the shutters, motors and other PVs named in
its conditions and serves four read-only status PVs per node. Here the file
is read only for the node structure: each node becomes a ``MapNode`` device
with those four status signals, and the whole map a ``BeamMap`` device. The
conditions and the PVs they name are never read.

Load it from devices.toml::

    [beam_map]
    _target = "nbs_bl.beam_map.BeamMapFactory"
    _role = "beam_map"
    map_file = "beam_map.toml"
    endstation = "es_chamber"

``endstation`` names the node whose beam this beamline cares about.
``beam_expected()`` and ``why_no_beam()`` answer for it, and ``publish``
keeps a JSON-able copy of the tree and every node's status in a status dict
(``BEAM_MAP``) for clients without EPICS access.
"""

import re
from datetime import datetime
from os.path import isabs, join

from ophyd import Component as Cpt
from ophyd import Device, EpicsSignalRO

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

FIELDS = ("blocking", "path_clear", "beam_expected", "reason")


class MapNode(Device):
    """One node of the beamline map: its four status PVs."""

    blocking = Cpt(EpicsSignalRO, "Blocking")
    path_clear = Cpt(EpicsSignalRO, "PathClear")
    beam_expected = Cpt(EpicsSignalRO, "BeamExpected")
    reason = Cpt(EpicsSignalRO, "Reason", string=True)

    def __init__(self, *args, upstream=None, desc="", node_name=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.node_name = node_name
        self.upstream = upstream
        self.desc = desc
        self.children = []

    def status(self):
        """Read the node's four status PVs."""
        return {
            "blocking": bool(self.blocking.get()),
            "path_clear": bool(self.path_clear.get()),
            "beam_expected": bool(self.beam_expected.get()),
            "reason": self.reason.get(),
        }


def read_map_file(path):
    """
    Read the structure of a map file: its name, prefix and nodes.

    Returns
    -------
    dict
        ``name``, ``prefix`` and ``nodes`` (node name to ``upstream`` and
        ``desc``), in file order.
    """
    with open(path, "rb") as f:
        data = tomllib.load(f)
    meta = data.get("map", {})
    specs = data.get("nodes", {})
    for name, spec in specs.items():
        up = spec.get("upstream")
        if up is not None and up not in specs:
            raise ValueError(f"node {name}: upstream {up!r} is not a node")
    for name in specs:
        seen = {name}
        up = specs[name].get("upstream")
        while up is not None:
            if up in seen:
                raise ValueError(f"node {name}: upstream chain has a cycle")
            seen.add(up)
            up = specs[up].get("upstream")
    nodes = {
        name: {"upstream": spec.get("upstream"), "desc": spec.get("desc", "")}
        for name, spec in specs.items()
    }
    return {"name": meta.get("name", ""), "prefix": meta.get("prefix", ""), "nodes": nodes}


def _attr_name(node, taken):
    """A Python attribute name for ``node``; the PV name keeps the node name."""
    attr = re.sub(r"\W", "_", node)
    if not attr or attr[0].isdigit() or hasattr(BeamMap, attr):
        attr = f"node_{attr}"
    while attr in taken:
        attr += "_"
    return attr


def beam_map_class(spec):
    """Build a BeamMap subclass with one MapNode component per node of ``spec``."""
    attrs = {}
    for node, info in spec["nodes"].items():
        attr = _attr_name(node, attrs)
        attrs[attr] = Cpt(
            MapNode,
            f"{node}:",
            upstream=info["upstream"],
            desc=info["desc"],
            node_name=node,
        )
    cls_name = "BeamMap_" + (re.sub(r"\W", "_", spec["name"]) or "map")
    return type(cls_name, (BeamMap,), attrs)


class BeamMap(Device):
    """
    The beamline map: a MapNode device per node, plus the node tree.

    Built by ``beam_map_class``; use ``BeamMapFactory`` to load one from a
    map file.
    """

    def __init__(self, *args, map_spec, endstation=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.map_name = map_spec["name"]
        self.nodes = {}
        for attr in self.component_names:
            node = getattr(self, attr)
            if isinstance(node, MapNode):
                self.nodes[node.node_name] = node
        for node in self.nodes.values():
            if node.upstream is not None:
                self.nodes[node.upstream].children.append(node.node_name)
        if endstation is not None and endstation not in self.nodes:
            print(f"Beam map: endstation {endstation!r} is not a node, ignoring it")
            endstation = None
        self.endstation = endstation
        self._published = None
        self._status = {}

    def roots(self):
        return [n for n, node in self.nodes.items() if node.upstream is None]

    def _node(self, node):
        node = node or self.endstation
        if node is None:
            raise ValueError("No node given and no endstation set for the beam map")
        return self.nodes[node]

    def status(self, node=None):
        return self._node(node).status()

    def beam_expected(self, node=None):
        """Whether beam is expected at ``node`` (default: the endstation)."""
        return bool(self._node(node).beam_expected.get())

    def why_no_beam(self, node=None):
        """Why there is no beam at ``node`` (default: the endstation), or ""."""
        return self._node(node).reason.get()

    def beam_status(self, node=None):
        """Beam expected and the reason, for ``node`` (default: the endstation)."""
        name = self._node(node).node_name
        return {
            "endstation": name,
            "beam_expected": self.beam_expected(name),
            "reason": self.why_no_beam(name),
        }

    def to_dict(self):
        """The tree and the last known status of every node, JSON-able."""
        nodes = {}
        for name, node in self.nodes.items():
            entry = {
                "upstream": node.upstream,
                "children": list(node.children),
                "desc": node.desc,
            }
            entry.update(self._status.get(name, dict.fromkeys(FIELDS)))
            nodes[name] = entry
        out = {
            "name": self.map_name,
            "prefix": self.prefix,
            "endstation": self.endstation,
            "nodes": nodes,
        }
        es = nodes.get(self.endstation, {})
        out["beam_expected"] = es.get("beam_expected")
        out["reason"] = es.get("reason")
        return out

    def publish(self, status_dict):
        """
        Keep ``status_dict`` up to date with ``to_dict()``, from subscriptions
        to every status signal.
        """
        self._published = status_dict
        for name, node in self.nodes.items():
            self._status[name] = dict.fromkeys(FIELDS)
            for field in FIELDS:
                getattr(node, field).subscribe(self._make_callback(name, field))
        self._write()

    def _make_callback(self, name, field):
        def callback(value=None, **kwargs):
            if field != "reason" and value is not None:
                value = bool(value)
            self._status[name][field] = value
            self._write()

        return callback

    def _write(self):
        if self._published is None:
            return
        data = self.to_dict()
        data["updated"] = datetime.now().isoformat(timespec="seconds")
        self._published.update(data)


def BeamMapFactory(map_file, *, name="beam_map", prefix=None, endstation=None, **kwargs):
    """
    Load a BeamMap device from a map file.

    Parameters
    ----------
    map_file : str
        Path to the map file. A relative path is taken from the startup
        directory, so a central map can later be given as an absolute path.
    name : str
        Device name.
    prefix : str, optional
        Status PV prefix; defaults to the map file's ``[map] prefix``.
    endstation : str, optional
        Node that ``beam_expected()`` and ``why_no_beam()`` answer for.
    """
    if not isabs(map_file):
        from .beamline import GLOBAL_BEAMLINE

        startup_dir = GLOBAL_BEAMLINE.settings.get("startup_dir")
        if startup_dir:
            map_file = join(startup_dir, map_file)
    spec = read_map_file(map_file)
    cls = beam_map_class(spec)
    prefix = spec["prefix"] if prefix is None else prefix
    return cls(prefix, name=name, map_spec=spec, endstation=endstation, **kwargs)


def _current_map():
    from .beamline import GLOBAL_BEAMLINE

    bmap = getattr(GLOBAL_BEAMLINE, "beam_map", None)
    if bmap is None:
        raise RuntimeError("No beam map loaded")
    return bmap


def beam_expected(node=None):
    """Whether beam is expected at ``node`` (default: the endstation)."""
    return _current_map().beam_expected(node)


def why_no_beam(node=None):
    """Why there is no beam at ``node`` (default: the endstation), or ""."""
    return _current_map().why_no_beam(node)


def beam_status(node=None):
    """Beam expected and the reason, for ``node`` (default: the endstation)."""
    return _current_map().beam_status(node)
