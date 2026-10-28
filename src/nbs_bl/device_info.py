"""
Static description of the beamline's devices, for agents and clients
without EPICS access.

``device_info`` reports what each device is (class, beam map node, groups,
roles, the ``_desc``, ``_axes`` and ``_sample_frame`` notes from
devices.toml) and whether it is loaded. It never reads a signal, and never
copies a prefix or any other constructor argument, so its output holds no PV
names. ``SetupDeviceInfoStep`` publishes it once at startup to the
``DEVICE_INFO`` status dict.
"""

from .utils import iterfy


def _class_name(device, entry):
    if device is not None:
        return type(device).__name__
    target = entry.get("_target")
    if isinstance(target, str):
        return target.split(".")[-1]
    return None


def _node(beamline, name, entry):
    bmap = getattr(beamline, "beam_map", None)
    if bmap is not None:
        node = bmap.node_of(name)
        if node is not None:
            return node
    return entry.get("_node")


def _one_device(beamline, name, entry):
    device = beamline.devices.get(name)
    loaded = device is not None
    groups = entry.get("_group")
    if groups is None and ("_target" in entry or "_alias" in entry):
        groups = "misc"
    info = {
        "class": _class_name(device, entry),
        "node": _node(beamline, name, entry),
        "groups": list(iterfy(groups)) if groups is not None else [],
        "roles": [r for r in iterfy(entry.get("_role", [])) if r],
        "desc": entry.get("_desc"),
        "axes": entry.get("_axes"),
        "sample_frame": entry.get("_sample_frame"),
        "loaded": loaded,
        "deferred": name in getattr(beamline, "_deferred_devices", ()),
        "in_baseline": loaded and device in beamline.supplemental_data.baseline,
        "alias_of": entry.get("_alias"),
        "components": list(getattr(device, "component_names", ())) if loaded else [],
    }
    return {
        k: v for k, v in info.items()
        if k == "loaded" or v not in (None, "", [], {}, False)
    }


def device_info(names=None, beamline=None):
    """
    Static description of devices: class, node, groups, roles and notes.

    Parameters
    ----------
    names : str or list of str, optional
        Device names; all devices (loaded, deferred and aliases) if None.
    beamline : BeamlineModel, optional
        Defaults to GLOBAL_BEAMLINE.

    Returns
    -------
    dict
        ``{name: info}``, JSON-able. ``info`` has ``class``, ``node``,
        ``groups``, ``roles``, ``desc``, ``axes``, ``sample_frame``,
        ``loaded``, ``deferred``, ``in_baseline``, ``alias_of`` and
        ``components`` (top-level component names), with empty fields left
        out. An unknown name maps to ``{"error": "unknown device"}``.
    """
    if beamline is None:
        from .beamline import GLOBAL_BEAMLINE

        beamline = GLOBAL_BEAMLINE
    config = (getattr(beamline, "config", None) or {}).get("devices", {})
    if names is None:
        names = list(config) + [n for n in beamline.devices if n not in config]
    out = {}
    for name in iterfy(names):
        entry = config.get(name)
        if not isinstance(entry, dict):
            entry = {} if name in beamline.devices else None
        if entry is None:
            out[name] = {"error": "unknown device"}
        else:
            out[name] = _one_device(beamline, name, entry)
    return out
