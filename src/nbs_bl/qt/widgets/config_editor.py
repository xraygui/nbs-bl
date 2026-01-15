from __future__ import annotations

from pathlib import Path

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from nbs_bl.qt.models.config_model import ConfigIssue, ConfigModel


class ConfigEditorWidget(QWidget):
    """Widget for editing NBS-BL `devices.toml` files."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent=parent)
        self.model = ConfigModel(parent=self)
        self._current_device_key: str | None = None
        self._updating = False
        self._device_type_overrides: dict[str, str] = {}
        self._device_type_values: dict[str, dict[str, str]] = {}
        self._special_bool_defaults = {
            "_defer_loading": False,
            "_add_to_ns": True,
            "_baseline": True,
        }

        self._build_ui()
        self._connect_signals()
        self._refresh_device_list()
        self._set_current_device(None)

    def _build_ui(self) -> None:
        root = QVBoxLayout()

        self.file_label = QLabel("")
        self.file_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        root.addWidget(self.file_label)

        toolbar = QHBoxLayout()
        self.new_button = QPushButton("New")
        self.open_button = QPushButton("Open")
        self.save_button = QPushButton("Save")
        self.save_as_button = QPushButton("Save As")
        toolbar.addWidget(self.new_button)
        toolbar.addWidget(self.open_button)
        toolbar.addWidget(self.save_button)
        toolbar.addWidget(self.save_as_button)
        toolbar.addStretch(1)
        root.addLayout(toolbar)

        splitter = QSplitter()

        left = QWidget()
        left_layout = QVBoxLayout()
        left.setLayout(left_layout)
        self.device_list = QListWidget()
        self.device_list.setSelectionMode(QAbstractItemView.SingleSelection)
        left_layout.addWidget(self.device_list)

        left_buttons = QHBoxLayout()
        self.add_device_button = QPushButton("Add Device")
        self.remove_device_button = QPushButton("Remove Device")
        left_buttons.addWidget(self.add_device_button)
        left_buttons.addWidget(self.remove_device_button)
        left_layout.addLayout(left_buttons)

        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout()
        right.setLayout(right_layout)

        self.device_key_label = QLabel("")
        self.device_key_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        right_layout.addWidget(self.device_key_label)

        self.special_group = QGroupBox("Special Keys")
        special_form = QFormLayout()
        self.special_group.setLayout(special_form)

        self.device_type = QComboBox()
        self.device_type.addItems(["Target Class", "Alias"])

        self.type_value = QLineEdit()
        type_row = QWidget()
        type_row_layout = QHBoxLayout()
        type_row_layout.setContentsMargins(0, 0, 0, 0)
        type_row.setLayout(type_row_layout)
        type_row_layout.addWidget(self.device_type)
        type_row_layout.addWidget(self.type_value)

        self.group = QLineEdit()
        self.role = QLineEdit()
        self.modes = QLineEdit()

        self.defer_loading = QCheckBox()
        self.add_to_namespace = QCheckBox()
        self.baseline = QCheckBox()

        self.load_order = QSpinBox()
        self.load_order.setMinimum(-999999)
        self.load_order.setMaximum(999999)

        special_form.addRow("Type", type_row)
        special_form.addRow("Group", self.group)
        special_form.addRow("Role", self.role)
        special_form.addRow("Modes", self.modes)
        special_form.addRow("Defer Loading", self.defer_loading)
        special_form.addRow("Add to Namespace", self.add_to_namespace)
        special_form.addRow("Baseline", self.baseline)
        special_form.addRow("Load Order", self.load_order)

        right_layout.addWidget(self.special_group)

        self.normal_group = QGroupBox("Normal Keys")
        normal_layout = QVBoxLayout()
        self.normal_group.setLayout(normal_layout)

        normal_form = QFormLayout()
        self.ophyd_name = QLineEdit()
        self.prefix = QLineEdit()
        normal_form.addRow("Name", self.ophyd_name)
        normal_form.addRow("Prefix", self.prefix)
        normal_layout.addLayout(normal_form)

        self.extra_table = QTableWidget()
        self.extra_table.setColumnCount(2)
        self.extra_table.setHorizontalHeaderLabels(["Key", "Value"])
        self.extra_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.extra_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.extra_table.verticalHeader().setVisible(False)
        self.extra_table.horizontalHeader().setStretchLastSection(True)
        normal_layout.addWidget(self.extra_table)

        extra_buttons = QHBoxLayout()
        self.add_key_button = QPushButton("Add Key")
        self.remove_key_button = QPushButton("Remove Key")
        extra_buttons.addWidget(self.add_key_button)
        extra_buttons.addWidget(self.remove_key_button)
        extra_buttons.addStretch(1)
        normal_layout.addLayout(extra_buttons)

        right_layout.addWidget(self.normal_group)

        self.validation_group = QGroupBox("Validation")
        validation_layout = QVBoxLayout()
        self.validation_group.setLayout(validation_layout)
        self.validation_list = QListWidget()
        validation_layout.addWidget(self.validation_list)
        self.remove_unknown_button = QPushButton("Remove Unknown Special Keys")
        validation_layout.addWidget(self.remove_unknown_button)
        right_layout.addWidget(self.validation_group)

        right_layout.addStretch(1)
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        root.addWidget(splitter)
        self.setLayout(root)

        self._update_type_placeholder()
        self._update_file_label()

    def _connect_signals(self) -> None:
        self.new_button.clicked.connect(self._new_file)
        self.open_button.clicked.connect(self._open_file)
        self.save_button.clicked.connect(self._save_file)
        self.save_as_button.clicked.connect(self._save_file_as)

        self.add_device_button.clicked.connect(self._add_device)
        self.remove_device_button.clicked.connect(self._remove_device)
        self.device_list.currentItemChanged.connect(self._on_device_item_changed)

        self.device_type.currentTextChanged.connect(self._on_type_changed)
        self.type_value.editingFinished.connect(self._on_special_edited)
        self.group.editingFinished.connect(self._on_special_edited)
        self.role.editingFinished.connect(self._on_special_edited)
        self.modes.editingFinished.connect(self._on_special_edited)
        self.defer_loading.stateChanged.connect(self._on_special_edited)
        self.add_to_namespace.stateChanged.connect(self._on_special_edited)
        self.baseline.stateChanged.connect(self._on_special_edited)
        self.load_order.valueChanged.connect(self._on_special_edited)

        self.ophyd_name.editingFinished.connect(self._on_normal_edited)
        self.prefix.editingFinished.connect(self._on_normal_edited)
        self.add_key_button.clicked.connect(self._add_extra_key)
        self.remove_key_button.clicked.connect(self._remove_extra_key)
        self.extra_table.itemChanged.connect(self._on_extra_item_changed)
        self.remove_unknown_button.clicked.connect(self._remove_unknown_special_keys)

        self.model.changed.connect(self._refresh_device_list)
        self.model.issues_changed.connect(self._refresh_validation)
        self.model.file_path_changed.connect(self._update_file_label)
        self.model.dirty_changed.connect(self._update_file_label)

    def _update_file_label(self) -> None:
        suffix = " (modified)" if self.model.dirty else ""
        if self.model.file_path is None:
            self.file_label.setText(f"File: (unsaved){suffix}")
        else:
            self.file_label.setText(f"File: {self.model.file_path}{suffix}")

    def _refresh_device_list(self) -> None:
        current = self._current_device_key
        self.device_list.blockSignals(True)
        self.device_list.clear()
        for key in self.model.device_keys():
            text = f"{key} *" if self.model.is_device_dirty(key) else key
            self.device_list.addItem(text)
            self.device_list.item(self.device_list.count() - 1).setData(Qt.UserRole, key)
        self.device_list.blockSignals(False)

        if current in self.model.devices:
            for i in range(self.device_list.count()):
                item = self.device_list.item(i)
                if item is not None and item.data(Qt.UserRole) == current:
                    self.device_list.setCurrentItem(item)
                    break
        elif self.model.device_keys():
            self.device_list.setCurrentRow(0)
        else:
            self._set_current_device(None)

    def _on_device_item_changed(self, current, previous) -> None:
        if current is None:
            self._set_current_device(None)
            return
        key = current.data(Qt.UserRole)
        self._set_current_device(str(key) if key is not None else current.text())

    def _set_current_device(self, device_key: str | None) -> None:
        self._current_device_key = device_key if device_key else None
        if self._current_device_key is None:
            self.device_key_label.setText("No device selected")
            self._set_editor_enabled(False)
            self._clear_editor()
            return
        self.device_key_label.setText(f"Device Key: {self._current_device_key}")
        self._set_editor_enabled(True)
        self._load_device_to_editor(self._current_device_key)

    def _set_editor_enabled(self, enabled: bool) -> None:
        self.special_group.setEnabled(enabled)
        self.normal_group.setEnabled(enabled)

    def _clear_editor(self) -> None:
        self._updating = True
        try:
            self.device_type.setCurrentText("Target Class")
            self.type_value.setText("")
            self.group.setText("")
            self.role.setText("")
            self.modes.setText("")
            self.defer_loading.setChecked(bool(self._special_bool_defaults["_defer_loading"]))
            self.add_to_namespace.setChecked(bool(self._special_bool_defaults["_add_to_ns"]))
            self.baseline.setChecked(bool(self._special_bool_defaults["_baseline"]))
            self.load_order.setValue(0)
            self.ophyd_name.setText("")
            self.prefix.setText("")
            self.extra_table.setRowCount(0)
            self.validation_list.clear()
            self._update_type_placeholder()
            self._update_normal_keys_enabled()
        finally:
            self._updating = False

    def _load_device_to_editor(self, device_key: str) -> None:
        config = self.model.get_device_config(device_key)
        self._updating = True
        try:
            if device_key not in self._device_type_values:
                self._device_type_values[device_key] = {"Target Class": "", "Alias": ""}
            if "_target" in config and isinstance(config.get("_target"), str):
                self._device_type_values[device_key]["Target Class"] = str(config.get("_target"))
            if "_alias" in config and isinstance(config.get("_alias"), str):
                self._device_type_values[device_key]["Alias"] = str(config.get("_alias"))

            if "_alias" in config and "_target" not in config:
                selected_type = "Alias"
            elif "_target" in config and "_alias" not in config:
                selected_type = "Target Class"
            else:
                selected_type = self._device_type_overrides.get(device_key, "Target Class")

            self.device_type.setCurrentText(selected_type)
            self.type_value.setText(self._device_type_values.get(device_key, {}).get(selected_type, ""))

            group_val = config.get("_group", "")
            if isinstance(group_val, list):
                self.group.setText(", ".join(group_val))
            else:
                self.group.setText(str(group_val) if group_val is not None else "")

            self.role.setText(str(config.get("_role", "")) if "_role" in config else "")

            modes_val = config.get("_modes", "")
            if isinstance(modes_val, list):
                self.modes.setText(", ".join(modes_val))
            else:
                self.modes.setText("")

            self.defer_loading.setChecked(self._get_bool_with_default(config, "_defer_loading"))
            self.add_to_namespace.setChecked(self._get_bool_with_default(config, "_add_to_ns"))
            self.baseline.setChecked(self._get_bool_with_default(config, "_baseline"))

            load_order_val = config.get("_load_order", 0)
            self.load_order.setValue(int(load_order_val) if isinstance(load_order_val, int) else 0)

            self.ophyd_name.setText(str(config.get("name", "")) if "name" in config else "")
            self.prefix.setText(str(config.get("prefix", "")) if "prefix" in config else "")

            self._populate_extra_table(config)
            self._update_type_placeholder()
            self._update_normal_keys_enabled()
        finally:
            self._updating = False

        self._refresh_validation(self.model.issues)

    def _populate_extra_table(self, config: dict) -> None:
        excluded = set(self.model.SPECIAL_KEYS) | {"name", "prefix"}
        extra_items = [
            (k, v)
            for k, v in config.items()
            if k not in excluded and not (isinstance(k, str) and k.startswith("_"))
        ]
        self.extra_table.blockSignals(True)
        self.extra_table.setRowCount(0)
        for key, value in extra_items:
            row = self.extra_table.rowCount()
            self.extra_table.insertRow(row)
            key_item = QTableWidgetItem(str(key))
            key_item.setData(Qt.UserRole, str(key))
            val_item = QTableWidgetItem(self._value_to_text(value))
            self.extra_table.setItem(row, 0, key_item)
            self.extra_table.setItem(row, 1, val_item)
        self.extra_table.blockSignals(False)

    def _refresh_validation(self, issues: list[ConfigIssue]) -> None:
        self.validation_list.clear()
        if not issues:
            self.validation_list.addItem("No issues")
            return
        for issue in issues:
            self.validation_list.addItem(f"{issue.device_key}: {issue.message}")

    def _value_to_text(self, value: object) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, list):
            parts = []
            for v in value:
                if isinstance(v, str):
                    parts.append(f'"{v}"')
                else:
                    parts.append(str(v))
            return f"[{', '.join(parts)}]"
        return str(value)

    def _update_type_placeholder(self) -> None:
        if self.device_type.currentText() == "Alias":
            self.type_value.setPlaceholderText("Alias")
        else:
            self.type_value.setPlaceholderText("Target class path")

    def _update_normal_keys_enabled(self) -> None:
        enabled = self._current_device_key is not None and self.device_type.currentText() != "Alias"
        self.normal_group.setEnabled(enabled)

    def _get_bool_with_default(self, config: dict, key: str) -> bool:
        default = bool(self._special_bool_defaults[key])
        if key not in config:
            return default
        value = config.get(key)
        return value if isinstance(value, bool) else default

    def _on_type_changed(self) -> None:
        if self._current_device_key is not None:
            key = self._current_device_key
            self._device_type_overrides[key] = self.device_type.currentText()
            if key not in self._device_type_values:
                self._device_type_values[key] = {"Target Class": "", "Alias": ""}
        self._update_type_placeholder()
        self._update_normal_keys_enabled()
        if self._current_device_key is None:
            return
        key = self._current_device_key
        current_type = self.device_type.currentText()
        self._updating = True
        try:
            self.type_value.setText(self._device_type_values.get(key, {}).get(current_type, ""))
        finally:
            self._updating = False
        self._apply_type_selection_to_config()

    def _apply_type_selection_to_config(self) -> None:
        if self._current_device_key is None:
            return
        key = self._current_device_key
        config = self.model.get_device_config(key)
        selected_type = self.device_type.currentText()

        if key not in self._device_type_values:
            self._device_type_values[key] = {"Target Class": "", "Alias": ""}

        if selected_type == "Alias":
            config.pop("_target", None)
            alias_text = self._device_type_values[key].get("Alias", "").strip()
            if alias_text:
                config["_alias"] = alias_text
            else:
                config.pop("_alias", None)
            for k in list(config.keys()):
                if isinstance(k, str) and not k.startswith("_"):
                    config.pop(k, None)
        else:
            config.pop("_alias", None)
            target_text = self._device_type_values[key].get("Target Class", "").strip()
            if target_text:
                config["_target"] = target_text
            else:
                config.pop("_target", None)

        self.model.set_device_config(key, config)

    def _on_special_edited(self) -> None:
        if self._updating or self._current_device_key is None:
            return

        key = self._current_device_key
        config = self.model.get_device_config(key)

        if key not in self._device_type_values:
            self._device_type_values[key] = {"Target Class": "", "Alias": ""}

        if self.device_type.currentText() == "Alias":
            alias_text = self.type_value.text().strip()
            self._device_type_values[key]["Alias"] = alias_text
            config.pop("_target", None)
            if alias_text:
                config["_alias"] = alias_text
            else:
                config.pop("_alias", None)
            for k in list(config.keys()):
                if isinstance(k, str) and not k.startswith("_"):
                    config.pop(k, None)
        else:
            target_text = self.type_value.text().strip()
            self._device_type_values[key]["Target Class"] = target_text
            config.pop("_alias", None)
            if target_text:
                config["_target"] = target_text
            else:
                config.pop("_target", None)

        group_text = self.group.text().strip()
        if group_text:
            parts = [p.strip() for p in group_text.split(",") if p.strip()]
            if len(parts) == 1:
                config["_group"] = parts[0]
            else:
                config["_group"] = parts
        else:
            config.pop("_group", None)

        role_text = self.role.text().strip()
        if role_text:
            config["_role"] = role_text
        else:
            config.pop("_role", None)

        modes_text = self.modes.text().strip()
        if modes_text:
            parts = [p.strip() for p in modes_text.split(",") if p.strip()]
            config["_modes"] = parts
        else:
            config.pop("_modes", None)

        for key_name, widget in (
            ("_defer_loading", self.defer_loading),
            ("_add_to_ns", self.add_to_namespace),
            ("_baseline", self.baseline),
        ):
            default = bool(self._special_bool_defaults[key_name])
            value = bool(widget.isChecked())
            if value == default:
                config.pop(key_name, None)
            else:
                config[key_name] = value

        load_order_val = int(self.load_order.value())
        if load_order_val == 0:
            config.pop("_load_order", None)
        else:
            config["_load_order"] = load_order_val

        self.model.set_device_config(key, config)
        self._update_normal_keys_enabled()

    def _on_normal_edited(self) -> None:
        if self._updating or self._current_device_key is None:
            return

        key = self._current_device_key
        config = self.model.get_device_config(key)

        name_text = self.ophyd_name.text()
        prefix_text = self.prefix.text()

        if name_text.strip() == "":
            config.pop("name", None)
        else:
            config["name"] = name_text

        if prefix_text.strip() == "":
            config.pop("prefix", None)
        else:
            config["prefix"] = prefix_text

        self.model.set_device_config(key, config)

    def _add_extra_key(self) -> None:
        if self._current_device_key is None:
            return
        row = self.extra_table.rowCount()
        self.extra_table.insertRow(row)
        key_item = QTableWidgetItem("")
        key_item.setData(Qt.UserRole, "")
        val_item = QTableWidgetItem("")
        self.extra_table.setItem(row, 0, key_item)
        self.extra_table.setItem(row, 1, val_item)
        self.extra_table.setCurrentCell(row, 0)

    def _remove_extra_key(self) -> None:
        if self._current_device_key is None:
            return
        rows = self.extra_table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        key_item = self.extra_table.item(row, 0)
        prev_key = key_item.data(Qt.UserRole) if key_item is not None else ""
        if prev_key:
            self.model.unset_value(self._current_device_key, str(prev_key))
        self.extra_table.removeRow(row)

    def _on_extra_item_changed(self, item: QTableWidgetItem) -> None:
        if self._updating or self._current_device_key is None:
            return
        row = item.row()
        key_item = self.extra_table.item(row, 0)
        val_item = self.extra_table.item(row, 1)
        if key_item is None or val_item is None:
            return

        new_key = key_item.text().strip()
        prev_key = str(key_item.data(Qt.UserRole) or "").strip()
        value_text = val_item.text()

        if prev_key and prev_key != new_key:
            self.model.unset_value(self._current_device_key, prev_key)

        if new_key == "":
            key_item.setData(Qt.UserRole, "")
            return

        if new_key.startswith("_"):
            QMessageBox.warning(
                self,
                "Reserved Key",
                "Keys beginning with '_' are special keys and are edited in the Special Keys section.",
            )
            self._updating = True
            try:
                key_item.setText(prev_key)
            finally:
                self._updating = False
            return

        value = self.model.parse_value_text(value_text)
        self.model.set_value(self._current_device_key, new_key, value)
        key_item.setData(Qt.UserRole, new_key)

    def _add_device(self) -> None:
        device_key, ok = QInputDialog.getText(self, "Add Device", "Device key")
        if not ok:
            return
        key = device_key.strip()
        if key == "":
            return
        try:
            self.model.add_device(key)
            items = self.device_list.findItems(key, Qt.MatchExactly)
            if items:
                self.device_list.setCurrentItem(items[0])
        except Exception as exc:
            QMessageBox.critical(self, "Add Device Failed", str(exc))

    def _remove_device(self) -> None:
        if self._current_device_key is None:
            return
        key = self._current_device_key
        ret = QMessageBox.question(
            self,
            "Remove Device",
            f"Remove device '{key}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if ret != QMessageBox.Yes:
            return
        self._device_type_overrides.pop(key, None)
        self._device_type_values.pop(key, None)
        self.model.remove_device(key)
        self._set_current_device(None)

    def _new_file(self) -> None:
        ret = QMessageBox.question(
            self,
            "New File",
            "Create a new configuration? Unsaved changes will be lost.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if ret != QMessageBox.Yes:
            return
        self.model.clear()
        self._refresh_device_list()

    def _open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open TOML", "", "TOML Files (*.toml)")
        if not path:
            return
        try:
            self.model.load_from_file(path)
        except Exception as exc:
            QMessageBox.critical(self, "Open Failed", str(exc))
            return
        self._refresh_device_list()

    def _save_file(self) -> None:
        if self.model.file_path is None:
            self._save_file_as()
            return
        self._save_with_warning(self.model.file_path)

    def _save_file_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save TOML", "", "TOML Files (*.toml)")
        if not path:
            return
        self._save_with_warning(Path(path))

    def _save_with_warning(self, path: Path) -> None:
        if self.model.file_path is None or Path(self.model.file_path) != Path(path):
            msg = "Saving will rewrite the file and will not preserve TOML comments."
        else:
            msg = "Saving will rewrite the file and will not preserve TOML comments."
        ret = QMessageBox.question(
            self,
            "Save",
            msg,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if ret != QMessageBox.Yes:
            return
        try:
            self.model.save_to_file(path)
        except Exception as exc:
            QMessageBox.critical(self, "Save Failed", str(exc))

    def _remove_unknown_special_keys(self) -> None:
        if self._current_device_key is None:
            return
        key = self._current_device_key
        config = self.model.get_device_config(key)
        unknown = [
            k
            for k in list(config.keys())
            if isinstance(k, str) and k.startswith("_") and k not in self.model.SPECIAL_KEYS
        ]
        if not unknown:
            QMessageBox.information(self, "Remove Unknown Special Keys", "No unknown special keys found.")
            return
        ret = QMessageBox.question(
            self,
            "Remove Unknown Special Keys",
            "Remove unknown special keys from this device?\n\n" + "\n".join(unknown),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if ret != QMessageBox.Yes:
            return
        for k in unknown:
            config.pop(k, None)
        self.model.set_device_config(key, config)


class ConfigEditorMainWindow(QMainWindow):
    """Standalone window wrapper for the configuration editor."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent=parent)
        self.setWindowTitle("NBS-BL Config Editor")
        self.editor = ConfigEditorWidget(self)
        self.setCentralWidget(self.editor)
        self._build_menu()

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")

        new_action = file_menu.addAction("New")
        open_action = file_menu.addAction("Open")
        save_action = file_menu.addAction("Save")
        save_as_action = file_menu.addAction("Save As")
        file_menu.addSeparator()
        exit_action = file_menu.addAction("Exit")

        new_action.triggered.connect(self.editor._new_file)
        open_action.triggered.connect(self.editor._open_file)
        save_action.triggered.connect(self.editor._save_file)
        save_as_action.triggered.connect(self.editor._save_file_as)
        exit_action.triggered.connect(self.close)


def main() -> None:
    """Launch the configuration editor as a standalone application."""

    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication([])
    win = ConfigEditorMainWindow()
    win.resize(1100, 750)
    win.show()
    if owns_app:
        app.exec_()


if __name__ == "__main__":
    main()

