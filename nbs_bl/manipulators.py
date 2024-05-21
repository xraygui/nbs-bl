from sst_base.manipulator import Manipulator4AxBase, Manipulator1AxBase
from sst_base.motors import FlyableMotor, PrettyMotor
from .geometry.linalg import vec
from .motors import add_motor
from ophyd import Component as Cpt

# Note, multimesh is in sst_hw
manip_origin = vec(0, 0, 464, 0)


def add_manipulator(manipulator, description="", name=None):
    for p in manipulator.real_positioners:
        add_motor(p)


def manipulatorFactory4Ax(xPV, yPV, zPV, rPV):
    class Manipulator(Manipulator4AxBase):
        x = Cpt(FlyableMotor, xPV, name="x", kind='hinted')
        y = Cpt(FlyableMotor, yPV,  name="y", kind='hinted')
        z = Cpt(FlyableMotor, zPV,  name="z", kind='hinted')
        r = Cpt(FlyableMotor, rPV, name="r", kind='hinted')

    return Manipulator


def ManipulatorBuilder(prefix, *, name, **kwargs):
    Manipulator = manipulatorFactory4Ax("SampX}Mtr", "SampY}Mtr", "SampZ}Mtr", "SampTh}Mtr")
    return Manipulator(None, prefix, origin=manip_origin, name=name, **kwargs)

def ManipulatorBuilderNEXAFS(prefix, *, name, **kwargs):
    Manipulator = manipulatorFactory4Ax("SampX}Mtr", "SampY}Mtr", "SampZ}Mtr", "SampRot}Mtr")
    return Manipulator(None, prefix, origin=manip_origin, name=name, **kwargs)


def manipulatorFactory1Ax(xPV):
    class MultiMesh(Manipulator1AxBase):
        x = Cpt(PrettyMotor, xPV, name="Multimesh")

    return MultiMesh


def MultiMeshBuilder(prefix, *, name, **kwargs):
    MultiMesh = manipulatorFactory1Ax("MMesh}Mtr")
    return MultiMesh(None, prefix, name=name, **kwargs)
