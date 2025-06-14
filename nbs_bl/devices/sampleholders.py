from ophyd import PseudoPositioner, Device, Component as Cpt
from ophyd.pseudopos import (
    pseudo_position_argument,
    real_position_argument,
    PseudoSingle,
)
from nbs_bl.geometry.affine import Frame, find_rotation
from nbs_bl.devices import FlyableMotor
import numpy as np
import copy


class SampleHolderBase(Device):
    def __init__(self, *args, attachment_point, holder=None, use_redis=True, **kwargs):
        """
        Parameters
        ----------
        holder : GeometryBase, optional
            A GeometryBase subclass that defines the geometry of a samplebar.
            If None, a holder will need to be set later via set_holder
        attachment_point : tuple
            Coordinates of the attachment point in beam coordinates.
            I.e, the motor coordinates that will bring the attachment point into the beam.
        use_redis : bool, optional
            If True, uses Redis-backed status containers where appropriate
        """
        super().__init__(*args, **kwargs)
        self.manip_frame = Frame(origin=np.zeros_like(attachment_point))
        self.attachment_frame = self.manip_frame.make_child_frame(
            origin=attachment_point
        )
        self.set_holder(holder)

    @property
    def samples(self):
        if self.holder is not None:
            return self.holder.samples
        else:
            return {}

    def set_holder(self, holder):
        self.holder = holder
        if holder is not None:
            self.holder.attach_manipulator(self.attachment_frame)
            holder_md, holder_frames = self.holder.get_geometry()
            self.holder_md = holder_md
            self.holder_frames = holder_frames
        else:
            self.holder_md = {}
            self.holder_frames = {}

    def clear_holder(self):
        self.set_holder(None)

    def clear_samples(self):
        if self.holder is not None:
            self.holder.clear_samples()

    def add_sample(self, name, id, position, description="", origin="holder", **kwargs):
        if self.holder is not None:
            self.holder.add_sample(name, id, position, description, origin, **kwargs)

    def remove_sample(self, sample_id):
        if self.holder is not None:
            self.holder.remove_sample(sample_id)

    def set_sample(self, sample_id):
        if self.holder is not None:
            self.holder.set_sample(sample_id)

    def load_sample_dict(self, samples, clear=True):
        """
        Create a sample dictionary into a sampleholder

        Parameters
        ----------
        samples : Dict
            A dictionary whose keys are sample_id keys, and entries that are dictionaries containing
            at least 'name' and 'position' keys, and optionally a 'description' key. The format of
            the 'position' dictionary depends on the sampleholder that is being used. Additional items in the
            dictionary will be passed to the sampleholder add_sample function.description
        clear : Bool
            If True, clear existing samples from the sampleholder.
        """
        if clear:
            self.clear_samples()
        for sample_id, s in samples.items():
            sdict = copy.deepcopy(s)
            name = sdict.pop("name")
            description = sdict.pop("description", name)
            position = sdict.pop("position")
            self.add_sample(
                name,
                sample_id,
                position,
                description=description,
                **sdict,
            )

    def load_sample_file(self, filename, clear=True):
        if self.holder is not None:
            samples = self.holder.read_sample_file(filename)
            self.load_sample_dict(samples, clear=clear)

    def reload_sample_frames(self):
        """Reload sample frames from the persisted samples dictionary.

        This is useful when samples are loaded from a persistent database but
        the corresponding frames need to be reconstructed, such as when
        creating a new SampleHolder instance.

        Note: This requires a holder to be set and will skip any samples
        with origin="absolute" since those frames are stored directly.
        """
        if self.holder is not None:
            self.holder.clear_samples()
            for sample_id, sample in self.holder.samples.items():
                if sample["origin"] == "absolute":
                    self.holder.sample_frames[sample_id] = sample["position"]
                else:
                    self.holder.sample_frames[sample_id] = (
                        self.holder.make_sample_frame(sample["position"])
                    )

    def move_sample(self, sample_id, **positions):
        position = self.get_sample_position(sample_id, **positions)
        return self.move(position)

    def get_sample_position(self, sample_id, **positions):
        raise NotImplementedError("This method should be implemented by the subclass")


class Manipulator1AxBase(PseudoPositioner, SampleHolderBase):
    sx = Cpt(PseudoSingle)

    def __init__(self, *args, origin: float = 0, **kwargs):
        super().__init__(*args, attachment_point=[origin], **kwargs)

    def add_current_position_as_sample(self, name, id, description, **kwargs):
        coordinates = tuple(self.real_position)
        origin = "absolute"
        self.add_sample(
            name, id, {"coordinates": coordinates}, description, origin=origin, **kwargs
        )

    @pseudo_position_argument
    def forward(self, pp):
        """
        Takes a sample frame position and converts it into real manipulator coordinates
        """
        if self.holder is None:
            return self.RealPosition(pp.sx)

        current_frame = self.holder.get_current_frame()
        if isinstance(current_frame, Frame):
            (position,) = current_frame.to_frame(pp, self.manip_frame)
        else:
            frame_coords = current_frame.get("coordinates", [0])
            position = pp.sx + frame_coords[0]

        return self.RealPosition(position)

    @real_position_argument
    def inverse(self, rp):
        if self.holder is None:
            return self.PseudoPosition(rp.sx)

        current_frame = self.holder.get_current_frame()
        if isinstance(current_frame, Frame):
            (position,) = self.manip_frame.to_frame(rp, current_frame)
        else:
            frame_coords = current_frame.get("coordinates", [0])
            position = rp.sx - frame_coords[0]
        return self.PseudoPosition(position)

    def get_sample_position(self, sample_id=None, position=0):
        if sample_id is not None:
            self.set_sample(sample_id)
        return position


class Manipulator4AxBase(PseudoPositioner, SampleHolderBase):
    sx = Cpt(PseudoSingle)
    sy = Cpt(PseudoSingle)
    sz = Cpt(PseudoSingle)
    sr = Cpt(PseudoSingle)

    """
    An X, Y, Z, R sample positioner
    """

    # Really need a discrete manipulator that can be set to
    # one of several sample positions. May just be a sampleholder
    # Good argument for having sampleholder contain the motors, not
    # the other way around...?
    def __init__(self, *args, beam_direction=(0, -1, 0), rotation_ax=2, **kwargs):
        super().__init__(*args, **kwargs)
        self.beam_direction = beam_direction
        self.rotation_ax = rotation_ax
        self.ax1 = (rotation_ax + 1) % 3
        self.ax2 = (rotation_ax + 2) % 3
        self.default_coords = [0, 0, 0, 45]

    @pseudo_position_argument
    def forward(self, pp):
        """
        Takes a sample frame position and converts it into real manipulator coordinates
        """
        if self.holder is None:
            return self.RealPosition(*pp)

        sample_coords = pp[:-1]
        r = pp[-1]

        current_frame = self.holder.get_current_frame()
        if isinstance(current_frame, Frame):
            xp, yp, zp = current_frame.to_frame(
                sample_coords,
                self.manip_frame,
            )

            r = self.sample_rotation_to_manip_rotation(r)
            x, y, z = self.manip_frame.rotate_in_plane(
                (xp, yp, zp), r * np.pi / 180.0, ax1=self.ax1, ax2=self.ax2
            )
        else:
            frame_coords = current_frame.get("coordinates", [0, 0, 0, 0])
            x = sample_coords[0] + frame_coords[0]
            y = sample_coords[1] + frame_coords[1]
            z = sample_coords[2] + frame_coords[2]
            r += frame_coords[3]

        return self.RealPosition(x, y, z, r)

    @real_position_argument
    def inverse(self, rp):
        """
        Takes a real manipulator position and converts into frame coordinates
        """
        if self.holder is None:
            return self.PseudoPosition(*rp)

        real_coords = rp[:-1]
        current_frame = self.holder.get_current_frame()

        if isinstance(current_frame, Frame):
            r = self.manip_rotation_to_sample_rotation(rp[-1])
            xp, yp, zp = self.manip_frame.rotate_in_plane(
                real_coords, -rp[-1] * np.pi / 180.0, ax1=self.ax1, ax2=self.ax2
            )
            x, y, z = self.manip_frame.to_frame((xp, yp, zp), current_frame)
        else:
            frame_coords = current_frame.get("coordinates", [0, 0, 0, 0])
            x = rp[0] - frame_coords[0]
            y = rp[1] - frame_coords[1]
            z = rp[2] - frame_coords[2]
            r = rp[3] - frame_coords[3]

        return self.PseudoPosition(x, y, z, r)

    def add_current_position_as_sample(self, name, id, description, **kwargs):
        coordinates = tuple(self.real_position)
        origin = "absolute"
        self.add_sample(
            name, id, {"coordinates": coordinates}, description, origin=origin, **kwargs
        )

    def get_sample_position(self, sample_id=None, **positions):
        if sample_id is not None:
            self.set_sample(sample_id)
        if self.holder is not None and isinstance(
            self.holder.get_current_frame(), Frame
        ):
            position = [p for p in self.default_coords]
        else:
            position = [0, 0, 0, 0]
        if "x" in positions:
            position[0] = positions["x"]
        if "y" in positions:
            position[1] = positions["y"]
        if "z" in positions:
            position[2] = positions["z"]
        if "r" in positions:
            position[3] = positions["r"]
        return position

    def sample_rotation_to_manip_rotation(self, r):
        # Assumes that z-axis is the surface normal!!
        grazing = find_rotation(
            self.holder.get_current_frame(),
            (1, 0, 0),
            self.manip_frame,
            self.beam_direction,
            self.rotation_ax,
        )
        return grazing * 180.0 / np.pi + r

    def manip_rotation_to_sample_rotation(self, r):
        grazing = find_rotation(
            self.holder.get_current_frame(),
            (1, 0, 0),
            self.manip_frame,
            self.beam_direction,
            self.rotation_ax,
        )
        return r - grazing * 180.0 / np.pi


def manipulatorFactory4Ax(xPV, yPV, zPV, rPV):
    class Manipulator(Manipulator4AxBase):
        x = Cpt(FlyableMotor, xPV, name="x", kind="hinted")
        y = Cpt(FlyableMotor, yPV, name="y", kind="hinted")
        z = Cpt(FlyableMotor, zPV, name="z", kind="hinted")
        r = Cpt(FlyableMotor, rPV, name="r", kind="hinted")

    return Manipulator
