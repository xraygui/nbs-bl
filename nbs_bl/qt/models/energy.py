from ..widgets.energy import EnergyControl, EnergyMonitor
from nbs_gui.models import EnergyAxesModel, PVPositionerModel, PVModel


# Copied from ucal as an example
class EnergyModel:
    default_controller = EnergyControl
    default_monitor = EnergyMonitor

    def __init__(
        self,
        name,
        obj,
        group,
        long_name,
        **kwargs,
    ):
        print("Initializing Energy")
        self.name = name
        self.obj = obj
        self.energy = EnergyAxesModel(name, obj, group, name)
        self.grating_motor = PVPositionerModel(
            name=obj.monoen.gratingx.name,
            obj=obj.monoen.gratingx,
            group=group,
            long_name=f"{name} Grating",
        )
        self.cff = PVModel(
            obj.monoen.cff.name, obj.monoen.cff, group=group, long_name=f"{name} CFF"
        )
        self.group = group
        self.label = long_name
        for key, value in kwargs.items():
            setattr(self, key, value)
        print("Done Initializing Energy")
