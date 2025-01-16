from qtpy.QtWidgets import (
    QGroupBox,
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
    QPushButton,
    QMessageBox,
    QDialog,
)
from nbs_gui.views.views import AutoControl, AutoMonitor
from nbs_gui.views.motor import MotorMonitor
from bluesky_queueserver_api import BPlan


class EnergyMonitor(QGroupBox):
    """Display widget for monitoring energy-related components.

    Parameters
    ----------
    energy : object
        Energy model containing energy, gap, and phase attributes
    parent_model : object
        Parent model containing beamline configuration
    orientation : str, optional
        Layout orientation
    *args, **kwargs
        Additional arguments passed to QGroupBox
    """

    def __init__(self, energy, parent_model, *args, orientation=None, **kwargs):
        print("Initializing EnergyMonitor")
        super().__init__("Energy Monitor", *args, **kwargs)
        vbox1 = QVBoxLayout()

        print("Adding energy monitor")
        vbox1.addWidget(AutoMonitor(energy.energy, parent_model))

        has_slits = (
            hasattr(parent_model.beamline, "slits")
            and parent_model.beamline.slits is not None
        )
        if has_slits:
            print("Adding slits monitor")
            vbox1.addWidget(AutoMonitor(parent_model.beamline.slits, parent_model))

        print("Adding CFF monitor")
        vbox1.addWidget(AutoMonitor(energy.cff, parent_model))

        print("Adding grating motor monitor")
        if hasattr(energy, "grating_motor"):
            vbox1.addWidget(MotorMonitor(energy.grating_motor, parent_model))

        self.setLayout(vbox1)
        print("EnergyMonitor initialization complete")


class EnergyControl(QGroupBox):
    """Widget for controlling energy-related components.

    Parameters
    ----------
    energy : object
        Energy model containing energy, gap, and phase attributes
    parent_model : object
        Parent model containing beamline configuration
    orientation : str, optional
        Layout orientation
    *args, **kwargs
        Additional arguments passed to QGroupBox
    """

    def __init__(self, energy, parent_model, *args, orientation=None, **kwargs):
        print("Initializing EnergyControl")
        super().__init__("Energy Control", *args, **kwargs)

        self.model = energy
        self.parent_model = parent_model
        self.REClientModel = parent_model.run_engine

        print("Creating Energy Control layout")
        vbox = QVBoxLayout()
        hbox = QHBoxLayout()
        ebox = QHBoxLayout()

        print("Adding energy control")
        if hasattr(energy, "energy"):
            ebox.addWidget(AutoControl(energy.energy, parent_model))

        has_slits = (
            hasattr(parent_model.beamline, "slits")
            and parent_model.beamline.slits is not None
        )
        if has_slits:
            print("Adding exit slit control")
            ebox.addWidget(AutoControl(parent_model.beamline.slits, parent_model))

        vbox.addLayout(ebox)
        hbox = QHBoxLayout()

        print("Adding CFF and grating monitors")
        if hasattr(energy, "cff"):
            hbox.addWidget(AutoMonitor(energy.cff, parent_model))
        if hasattr(energy, "grating_motor"):
            hbox.addWidget(AutoMonitor(energy.grating_motor, parent_model))

        self.advancedControlButton = QPushButton("Advanced Controls")
        self.advancedControlButton.clicked.connect(self.showAdvancedControls)
        hbox.addWidget(self.advancedControlButton)
        vbox.addLayout(hbox)
        self.setLayout(vbox)
        print("EnergyControl initialization complete")

    def showAdvancedControls(self):
        """Show the Advanced Energy Control dialog."""
        print("Opening advanced controls dialog")
        self.advancedDialog = QDialog(self)
        self.advancedDialog.setWindowTitle("Advanced Energy Control")
        layout = QVBoxLayout()
        advancedControl = AdvancedEnergyControl(
            self.model, self.parent_model, self.advancedDialog
        )
        layout.addWidget(advancedControl)
        self.advancedDialog.setLayout(layout)
        self.advancedDialog.exec_()


class AdvancedEnergyControl(QGroupBox):
    """Advanced controls for energy-related components.

    Parameters
    ----------
    model : object
        Energy model containing energy, gap, and phase attributes
    parent_model : object
        Parent model containing beamline configuration
    parent : QWidget, optional
        Parent widget
    """

    def __init__(self, model, parent_model, parent=None):
        print("Initializing AdvancedEnergyControl")
        super().__init__("Advanced Energy Control", parent)
        self.model = model
        self.parent_model = parent_model
        self.REClientModel = parent_model.run_engine

        layout = QVBoxLayout()

        print("Adding CFF control")
        if hasattr(model, "cff"):
            layout.addWidget(AutoControl(model.cff, parent_model))

        print("Creating grating controls")
        hbox = QHBoxLayout()
        if hasattr(model, "grating_motor"):
            hbox.addWidget(MotorMonitor(model.grating_motor, parent_model))

            print("Setting up grating selection")
            cb = QComboBox()
            self.cb = cb
            if hasattr(model.grating_motor.obj.setpoint, "enum_strs"):
                for n, s in enumerate(model.grating_motor.obj.setpoint.enum_strs):
                    if s != "":
                        cb.addItem(s, n)

            self.button = QPushButton("Change Grating")
            self.button.clicked.connect(self.change_grating)
            hbox.addWidget(cb)
            hbox.addWidget(self.button)

            self.tuneButton = QPushButton("Tune grating offsets")
            self.tuneButton.clicked.connect(self.tune_grating)
            hbox.addWidget(self.tuneButton)

        layout.addLayout(hbox)
        self.setLayout(layout)
        print("AdvancedEnergyControl initialization complete")

    def tune_grating(self):
        """Execute grating tuning plan."""
        print("Initiating grating tune")
        msg = "Ensure beamline is opened to multimesh reference ladder for tune"
        if self.confirm_dialog(msg):
            plan = BPlan("tune_grating")
            self.REClientModel._client.item_execute(plan)

    def change_grating(self):
        """Execute grating change plan."""
        print("Initiating grating change")
        enum = self.cb.currentData()
        print(f"Selected grating enum: {enum}")
        msg = (
            "Are you sure you want to change gratings?\n"
            "Ensure beam is open to the multimesh.\n"
            "Grating change and tune will run as queue item"
        )
        if self.confirm_dialog(msg):
            plan = BPlan("change_grating", enum)
            self.REClientModel._client.item_execute(plan)

    def confirm_dialog(self, confirm_message):
        """Show a confirmation dialog.

        Parameters
        ----------
        confirm_message : str
            Message to display in the dialog

        Returns
        -------
        bool
            True if user confirmed, False otherwise
        """
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Question)
        msg.setText(confirm_message)
        msg.setStyleSheet("button-layout: 1")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)
        ret = msg.exec_()
        return ret == QMessageBox.Yes
