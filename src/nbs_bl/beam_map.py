"""
Beamline map backed by the map IOC's status PVs.

The map file (``beam_map.toml`` by default) is shared with the map IOC in
nbs-sim (``nbs-map-ioc``), which watches the shutters, motors and other PVs
named in its conditions and serves four read-only status PVs per node. This
module reads the file only for the node structure and subscribes to those
status PVs. It never reads the conditions or the PVs they name.
"""

from ophyd import EpicsSignalRO

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


class MapNode:
    """One node of the beamline map and its status signals."""

    def __init__(self, name, prefix, upstream=None, desc=""):
        self.name = name
        self.upstream = upstream
        self.desc = desc
        self.children = []
        base = f"{prefix}{name}:"
        sig_name = f"beam_map_{name}"
        self.blocking = EpicsSignalRO(base + "Blocking", name=f"{sig_name}_blocking")
        self.path_clear = EpicsSignalRO(
            base + "PathClear", name=f"{sig_name}_path_clear"
        )
        self.beam_expected = EpicsSignalRO(
            base + "BeamExpected", name=f"{sig_name}_beam_expected"
        )
        self.reason = EpicsSignalRO(
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

    def __init__(self, name, prefix, nodes):
        self.name = name
        self.prefix = prefix
        self.nodes = nodes

    def roots(self):
        return [n for n, node in self.nodes.items() if node.upstream is None]

    def status(self, node):
        return self.nodes[node].status()

    def why_no_beam(self, node):
        """Why there is no beam at ``node``, or "" if beam is expected."""
        return self.nodes[node].reason.get()


def load_beam_map(path, prefix=None):
    """Build the node tree from the map file at ``path``."""
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
        name: MapNode(name, prefix, spec.get("upstream"), spec.get("desc", ""))
        for name, spec in specs.items()
    }
    for node in nodes.values():
        if node.upstream is not None:
            nodes[node.upstream].children.append(node.name)
    return BeamMap(meta.get("name", ""), prefix, nodes)
