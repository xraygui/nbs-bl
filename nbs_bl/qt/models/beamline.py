from nbs_core.beamline import BeamlineModel


class SSTBeamlineModel(BeamlineModel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.energy.obj.rotation_motor = self.primary_manipulator.obj.r
        print("Finished loading BeamlineModel")
