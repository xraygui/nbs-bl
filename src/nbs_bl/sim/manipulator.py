from nbs_bl.devices.sampleholders import Manipulator4AxBase, Manipulator1AxBase
from nbs_bl.geometry.bars import Standard4SidedBar, Bar1d
from nbs_bl.devices.sampleholders import manipulatorFactory4Ax


def ManipulatorBuilder(prefix, *, name, **kwargs):
    holder = Standard4SidedBar(24.5, 215)
    origin = (0, 0, 464)
    Manipulator = manipulatorFactory4Ax(
        "SampX}Mtr", "SampY}Mtr", "SampZ}Mtr", "SampTh}Mtr"
    )
    return Manipulator(
        prefix, name=name, attachment_point=origin, holder=holder, **kwargs
    )
