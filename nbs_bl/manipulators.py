from .motors import add_motor


def add_manipulator(manipulator, description="", name=None):
    for p in manipulator.real_positioners:
        add_motor(p)
