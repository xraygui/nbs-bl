from ..widgets.energy import EnergyControl, EnergyMonitor
from sst_gui.models import EnergyAxesModel, PVPositionerModel, PVModel
from sst_gui.loaders import modelFromOphyd


def energyFromOphyd(prefix, group=None, label=None, **kwargs):
    return modelFromOphyd(prefix, group, label, modelClass=EnergyModel)


class EnergyModel:
    default_controller = EnergyControl
    default_monitor = EnergyMonitor

    def __init__(
        self,
        name,
        obj,
        group,
        label,
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
            label=f"{name} Grating",
        )
        self.cff = PVModel(
            obj.monoen.cff.name, obj.monoen.cff, group=group, label=f"{name} CFF"
        )
        self.group = group
        self.label = label
        for key, value in kwargs.items():
            setattr(self, key, value)
        print("Done Initializing Energy")
