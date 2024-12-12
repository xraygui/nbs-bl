from ophyd import Device

class DummyObject(Device):
    def __init__(self, *args, name, **kwargs):
        super().__init__(*args, name=name)
