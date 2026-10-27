"""
Beamline map backed by the map IOC's status PVs.

The map file (``beam_map.toml`` by default) is shared with the map IOC in
nbs-sim (``nbs-map-ioc``), which watches the shutters, motors and other PVs
named in its conditions and serves four read-only status PVs per node. This
module reads the file only for the node structure and subscribes to those
status PVs. It never reads the conditions or the PVs they name.

The ``endstation`` setting (beamline.toml) names the node whose beam this
beamline cares about. ``beam_expected()`` and ``why_no_beam()`` answer for
it, and ``publish`` keeps a JSON-able copy of the tree and every node's
status in a status dict (``BEAM_MAP``) for clients without EPICS access.
"""

from datetime import datetime

from ophyd import EpicsSignalRO

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


FIELDS = ("blocking", "path_clear", "beam_expected", "reason")


class MapNode:
    """One node of the beamline map and its status signals."""

    def __init__(self, name, prefix, upstream=None, desc="", signal_class=EpicsSignalRO):
        self.name = name
        self.upstream = upstream
        self.desc = desc
        self.children = []
        base = f"{prefix}{name}:"
        sig_name = f"beam_map_{name}"
        self.blocking = signal_class(base + "Blocking", name=f"{sig_name}_blocking")
        self.path_clear = signal_class(
            base + "PathClear", name=f"{sig_name}_path_clear"
        )
        self.beam_expected = signal_class(
            base + "BeamExpected", name=f"{sig_name}_beam_expected"
        )
        self.reason = signal_class(
            base + "Reason", name=f"{sig_name}_reason", string=True
        )

    def status(self):
        """Read the node's four status PVs."""
        return {
            "blocking": bool(self.blocking.get()),
            "path_clear": bool(self.path_clear.get()),
            "beam_expected": bool(self.beam_expected.get()),
            "reason": self.reason.get(),
        }


class BeamMap:
    """The node tree of a beamline map."""

    def __init__(self, name, prefix, nodes, endstation=None):
        self.name = name
        self.prefix = prefix
        self.nodes = nodes
        self.endstation = endstation
        self._published = None
        self._status = {}

    def roots(self):
        return [n for n, node in self.nodes.items() if node.upstream is None]

    def _node(self, node):
        node = node or self.endstation
        if node is None:
            raise ValueError("No node given and no endstation set in beamline.toml")
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
        name = self._node(node).name
        return {
            "endstation": name,
            "beam_expected": self.beam_expected(name),
            "reason": self.why_no_beam(name),
        }

    def to_dict(self):
        """The tree and the last known status of every node, JSON-able."""
        nodes = {}
        for name, node in self.nodes.items():
            entry = {"upstream": node.upstream, "children": list(node.children), "desc": node.desc}
            entry.update(self._status.get(name, dict.fromkeys(FIELDS)))
            nodes[name] = entry
        out = {"name": self.name, "prefix": self.prefix, "endstation": self.endstation, "nodes": nodes}
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


def load_beam_map(path, prefix=None, endstation=None, signal_class=EpicsSignalRO):
    """
    Build the node tree from the map file at ``path``.

    ``endstation`` names the node the status functions answer for. A name
    that isn't a node is reported and ignored.
    """
    with open(path, "rb") as f:
        data = tomllib.load(f)
    meta = data.get("map", {})
    prefix = meta.get("prefix", "") if prefix is None else prefix
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
        name: MapNode(
            name, prefix, spec.get("upstream"), spec.get("desc", ""), signal_class
        )
        for name, spec in specs.items()
    }
    for node in nodes.values():
        if node.upstream is not None:
            nodes[node.upstream].children.append(node.name)
    if endstation is not None and endstation not in nodes:
        print(f"Beam map: endstation {endstation!r} is not a node, ignoring it")
        endstation = None
    return BeamMap(meta.get("name", ""), prefix, nodes, endstation)


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
