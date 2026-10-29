from nbs_bl.devices.sampleholders import Manipulator4AxBase, Manipulator1AxBase
from nbs_bl.geometry.bars import Standard4SidedBar, Standard2SidedBar, Bar1d
from nbs_bl.devices.sampleholders import manipulatorFactory4Ax


def make_holder(holder="Standard4SidedBar", width=24.5, length=215, thickness=None):
    """Build a bar holder by name, as given in a device config."""
    if holder == "Standard4SidedBar":
        return Standard4SidedBar(width, length)
    elif holder == "Standard2SidedBar":
        if thickness is None:
            raise ValueError("Standard2SidedBar needs a thickness")
        return Standard2SidedBar(width, thickness, length)
    raise ValueError(f"Unknown holder {holder}")


def ManipulatorBuilder(
    prefix,
    *,
    name,
    holder="Standard4SidedBar",
    width=24.5,
    length=215,
    thickness=None,
    **kwargs,
):
    holder = make_holder(holder, width, length, thickness)
    origin = (0, 0, 464)
    Manipulator = manipulatorFactory4Ax(
        "SampX}Mtr", "SampY}Mtr", "SampZ}Mtr", "SampTh}Mtr"
    )
    return Manipulator(
        prefix, name=name, attachment_point=origin, holder=holder, **kwargs
    )
