from nbs_gui.models.beamline import GUIBeamlineModel


class SSTBeamlineModel(GUIBeamlineModel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            self.energy.obj.rotation_motor = self.primary_sampleholder.obj.r
        except AttributeError as e:
            print(f"Problem loading energy model: {e}")
        print("Finished loading BeamlineModel")
