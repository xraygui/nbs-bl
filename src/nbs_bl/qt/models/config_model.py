try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from qtpy.QtCore import QObject, Signal


@dataclass(frozen=True)
class ConfigIssue:
    """A validation issue found in a device configuration.

    Parameters
    ----------
    device_key : str
        The device table name in the TOML file.
    message : str
        A human-readable description of the issue.
    """

    device_key: str
    message: str


class ConfigModel(QObject):
    """Model for editing NBS-BL device TOML configuration files.

    This model is responsible for:
    - Loading/parsing TOML into a Python mapping
    - Serializing the mapping back to TOML
    - Providing a small validation layer for NBS-BL special keys
    - Translating special keys to/from human-readable GUI labels

    Notes
    -----
    This model does not attempt to preserve TOML comments. Saving will
    rewrite the file content.
    """

    changed = Signal()
    issues_changed = Signal(list)
    file_path_changed = Signal(object)
    dirty_changed = Signal(bool)

    SPECIAL_KEY_LABELS = {
        "_target": "Target Class",
        "_group": "Group",
        "_role": "Role",
        "_defer_loading": "Defer Loading",
        "_add_to_ns": "Add to Namespace",
        "_load_order": "Load Order",
        "_baseline": "Baseline",
        "_modes": "Modes",
        "_alias": "Alias",
    }

    SPECIAL_KEYS = set(SPECIAL_KEY_LABELS.keys())

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent=parent)
        self._devices: dict[str, dict[str, Any]] = {}
        self._saved_devices: dict[str, dict[str, Any]] = {}
        self._file_path: Path | None = None
        self._issues: list[ConfigIssue] = []
        self._label_to_key = {v: k for k, v in self.SPECIAL_KEY_LABELS.items()}
        self._dirty = False

    @property
    def file_path(self) -> Path | None:
        """Path to the currently loaded file, if any."""

        return self._file_path

    @property
    def devices(self) -> dict[str, dict[str, Any]]:
        """Return the device configuration mapping."""

        return self._devices

    @property
    def issues(self) -> list[ConfigIssue]:
        """Return current validation issues."""

        return self._issues

    @property
    def dirty(self) -> bool:
        """Whether the configuration has unsaved changes."""

        return self._dirty

    def is_device_dirty(self, device_key: str) -> bool:
        """Return whether a device has been modified since last load/save.

        Parameters
        ----------
        device_key : str
            Device key to check.

        Returns
        -------
        bool
            True if the device differs from the last saved snapshot.
        """

        return self._devices.get(device_key, {}) != self._saved_devices.get(device_key, {})

    def clear(self) -> None:
        """Clear all devices and reset file path."""

        self._devices = {}
        self._saved_devices = deepcopy(self._devices)
        self._file_path = None
        self._revalidate()
        self._update_dirty()
        self.file_path_changed.emit(self._file_path)
        self.changed.emit()

    def load_from_file(self, file_path: str | Path) -> None:
        """Load devices configuration from a TOML file.

        Parameters
        ----------
        file_path : str or pathlib.Path
            Path to a TOML file containing device tables.
        """

        path = Path(file_path)
        with path.open("rb") as f:
            data = tomllib.load(f)
        if not isinstance(data, dict):
            raise ValueError("Device config TOML must be a table of device tables")
        devices: dict[str, dict[str, Any]] = {}
        for key, value in data.items():
            if isinstance(value, dict):
                devices[str(key)] = dict(value)
            else:
                raise ValueError(f"Device '{key}' must be a table")
        self._devices = devices
        self._saved_devices = deepcopy(self._devices)
        self._file_path = path
        self._revalidate()
        self._update_dirty()
        self.file_path_changed.emit(self._file_path)
        self.changed.emit()

    def save_to_file(self, file_path: str | Path | None = None) -> None:
        """Save devices configuration to a TOML file.

        Parameters
        ----------
        file_path : str or pathlib.Path or None, optional
            Output path. If None, uses the currently loaded file path.
        """

        path = Path(file_path) if file_path is not None else self._file_path
        if path is None:
            raise ValueError("No file path provided for saving")

        text = self.dumps()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self._file_path = path
        self._saved_devices = deepcopy(self._devices)
        self._update_dirty()
        self.file_path_changed.emit(self._file_path)

    def dumps(self) -> str:
        """Serialize current devices mapping to TOML text.

        Returns
        -------
        str
            TOML representation of the devices mapping.
        """

        lines: list[str] = []
        for device_key, config in self._devices.items():
            lines.append(self._format_table_header(device_key))
            for key, value in config.items():
                lines.append(f"{self._format_key(key)} = {self._format_value(value)}")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def device_keys(self) -> list[str]:
        """Return device keys in display order."""

        return list(self._devices.keys())

    def get_device_config(self, device_key: str) -> dict[str, Any]:
        """Get a shallow copy of a device configuration."""

        return dict(self._devices.get(device_key, {}))

    def set_device_config(self, device_key: str, config: dict[str, Any]) -> None:
        """Replace a device configuration entirely."""

        self._devices[device_key] = dict(config)
        self._revalidate()
        self._update_dirty()
        self.changed.emit()

    def add_device(self, device_key: str) -> None:
        """Add a new device with an empty configuration."""

        if device_key in self._devices:
            raise ValueError(f"Device '{device_key}' already exists")
        self._devices[device_key] = {}
        self._revalidate()
        self._update_dirty()
        self.changed.emit()

    def remove_device(self, device_key: str) -> None:
        """Remove a device from the configuration."""

        self._devices.pop(device_key, None)
        self._revalidate()
        self._update_dirty()
        self.changed.emit()

    def set_value(self, device_key: str, key: str, value: Any) -> None:
        """Set a configuration key on a device."""

        if device_key not in self._devices:
            raise KeyError(device_key)
        self._devices[device_key][key] = value
        self._revalidate()
        self._update_dirty()
        self.changed.emit()

    def unset_value(self, device_key: str, key: str) -> None:
        """Remove a configuration key from a device."""

        if device_key not in self._devices:
            raise KeyError(device_key)
        self._devices[device_key].pop(key, None)
        self._revalidate()
        self._update_dirty()
        self.changed.emit()

    def special_key_to_label(self, key: str) -> str:
        """Convert a special TOML key to a GUI label."""

        return self.SPECIAL_KEY_LABELS.get(key, key)

    def label_to_special_key(self, label: str) -> str:
        """Convert a GUI label back to a TOML special key."""

        return self._label_to_key.get(label, label)

    def parse_value_text(self, text: str) -> Any:
        """Parse a user-provided value string into a TOML-compatible value.

        Parameters
        ----------
        text : str
            Text representing a TOML value.

        Returns
        -------
        Any
            Parsed value. If parsing fails, the original text is returned.
        """

        stripped = text.strip()
        if stripped == "":
            return ""
        try:
            parsed = tomllib.loads(f"v = {stripped}\n")
            return parsed["v"]
        except Exception:
            return text

    def _revalidate(self) -> None:
        issues = self.validate()
        self._issues = issues
        self.issues_changed.emit(issues)

    def _update_dirty(self) -> None:
        dirty = self._devices != self._saved_devices
        if dirty != self._dirty:
            self._dirty = dirty
            self.dirty_changed.emit(dirty)

    def validate(self) -> list[ConfigIssue]:
        """Validate device configurations for known special keys and types.

        Returns
        -------
        list[ConfigIssue]
            A list of issues found in the current configuration.
        """

        issues: list[ConfigIssue] = []
        for device_key, config in self._devices.items():
            if not isinstance(config, dict):
                issues.append(ConfigIssue(device_key, "Device table must be a mapping"))
                continue

            special_keys = [k for k in config.keys() if isinstance(k, str) and k.startswith("_")]
            for k in special_keys:
                if k not in self.SPECIAL_KEYS:
                    issues.append(ConfigIssue(device_key, f"Unknown special key: {k}"))

            has_target = "_target" in config
            has_alias = "_alias" in config
            if not has_target and not has_alias:
                issues.append(ConfigIssue(device_key, "Missing Target Class or Alias"))
            if has_target and not isinstance(config.get("_target"), str):
                issues.append(ConfigIssue(device_key, "Target Class must be a string"))
            if has_alias and not isinstance(config.get("_alias"), str):
                issues.append(ConfigIssue(device_key, "Alias must be a string"))

            if "_role" in config and not isinstance(config.get("_role"), str):
                issues.append(ConfigIssue(device_key, "Role must be a string"))

            if "_group" in config:
                group_val = config.get("_group")
                if isinstance(group_val, str):
                    pass
                elif isinstance(group_val, list) and all(isinstance(x, str) for x in group_val):
                    pass
                else:
                    issues.append(ConfigIssue(device_key, "Group must be a string or list of strings"))

            if "_modes" in config:
                modes_val = config.get("_modes")
                if not (isinstance(modes_val, list) and all(isinstance(x, str) for x in modes_val)):
                    issues.append(ConfigIssue(device_key, "Modes must be a list of strings"))

            if "_load_order" in config and not isinstance(config.get("_load_order"), int):
                issues.append(ConfigIssue(device_key, "Load Order must be an integer"))

            for bool_key, label in (
                ("_defer_loading", "Defer Loading"),
                ("_add_to_ns", "Add to Namespace"),
                ("_baseline", "Baseline"),
            ):
                if bool_key in config and not isinstance(config.get(bool_key), bool):
                    issues.append(ConfigIssue(device_key, f"{label} must be a boolean"))

        return issues

    def _format_table_header(self, name: str) -> str:
        if self._is_bare_key(name):
            return f"[{name}]"
        return f'[{self._format_string(name)}]'

    def _format_key(self, key: str) -> str:
        if self._is_bare_key(key):
            return key
        return self._format_string(key)

    def _format_value(self, value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, int):
            return str(value)
        if isinstance(value, float):
            return repr(value)
        if isinstance(value, str):
            return self._format_string(value)
        if isinstance(value, list):
            inner = ", ".join(self._format_value(v) for v in value)
            return f"[{inner}]"
        raise TypeError(f"Unsupported value type: {type(value).__name__}")

    def _format_string(self, s: str) -> str:
        escaped = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    def _is_bare_key(self, key: str) -> bool:
        if key == "":
            return False
        for ch in key:
            if not (ch.isalnum() or ch in ("_", "-", ".")):
                return False
        return True

