from abc import ABC, abstractmethod
from ophyd import PseudoPositioner, Device, Component as Cpt
from ophyd.pseudopos import (
    pseudo_position_argument,
    real_position_argument,
    _to_position_tuple,
    PseudoSingle,
)
from nbs_bl.geometry.affine import NullFrame, Frame, find_rotation
import numpy as np
from .queueserver import add_status
from .status import StatusDict


class SampleHolderBase(Device):
    def __init__(self, *args, attachment_point, holder=None, **kwargs):
        """
        holder: A GeometryBase subclass that defines the geometry of a samplebar.
            If None, a holder will need to be set later via set_holder
        attachment_point: Tuple that gives the coordinates of the attachment point in beam coordinates.
            I.e, the motor coordinates that will bring the attachment point into the beam.

        """
        super().__init__(*args, **kwargs)
        self.manip_frame = Frame(origin=np.zeros_like(attachment_point))
        self.attachment_frame = self.manip_frame.make_child_frame(
            origin=attachment_point
        )
        self.samples = StatusDict()
        add_status(self.name.upper() + "_SAMPLES", self.samples)
        self.sample_frames = {}
        self.holder_md = {}
        self.holder_frames = {}
        self.current_frame = self.attachment_frame
        self.current_sample = None
        self.set_holder(holder)

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
        self.samples = {}
        self.sample_frames = {}

    def clear_samples(self):
        self.samples = {}
        self.sample_frames = {}

    def add_sample(self, name, id, position, description="", **kwargs):
        sample_frame = self.holder.make_sample_frame(position)
        self.samples[id] = {
            "name": name,
            "description": description,
            "position": position,
            "sample_id": id,
            **kwargs,
        }
        self.sample_frames[id] = sample_frame

    def set_sample(self, sample_id):
        if sample_id in self.sample_frames:
            self.current_frame = self.sample_frames[sample_id]
            self.current_sample = self.samples[sample_id]
        elif sample_id in self.holder_frames:
            self.current_frame = self.holder_frames[sample_id]
            self.current_sample = self.holder_md[sample_id]


class Manipulator1AxBase(PseudoPositioner, SampleHolderBase):
    sx = Cpt(PseudoSingle)

    def __init__(self, *args, origin: float = 0, **kwargs):
        super().__init__(*args, attachment_point=[origin], **kwargs)

    @pseudo_position_argument
    def forward(self, pp):
        """
        Takes a sample frame position and converts it into real manipulator coordinates
        """
        (position,) = self.current_frame.to_frame(pp, self.manip_frame)
        return self.RealPosition(position)

    @real_position_argument
    def inverse(self, rp):
        (position,) = self.manip_frame.to_frame(rp, self.current_frame)
        return self.PseudoPosition(position)

    def move_sample(self, sample_id, position=0, **kwargs):
        if sample_id is not None:
            self.set_sample(sample_id)
        return self.move(position)


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

        bp = self.holder.frame_to_beam(*pp)
        if isinstance(bp, (float, int)):
            bp = (bp,)
        rp = self.beam_to_manip_frame(*bp)
        return self.RealPosition(*rp)
        """
        sample_coords = pp[:-1]
        r = pp[-1]
        xp, yp, zp = self.current_frame.to_frame(
            sample_coords,
            self.manip_frame,
        )
        r = self.sample_rotation_to_manip_rotation(r)
        x, y, z = self.manip_frame.rotate_in_plane(
            (xp, yp, zp), r * np.pi / 180.0, ax1=self.ax1, ax2=self.ax2
        )
        return self.RealPosition(x, y, z, r)

    @real_position_argument
    def inverse(self, rp):
        """
        Takes a real manipulator position and converts into frame coordinates

        bp = self.manip_to_beam_frame(*rp)
        pp = self.holder.beam_to_frame(*bp)
        if isinstance(pp, (float, int)):
            pp = (pp,)
        return self.PseudoPosition(*pp)
        """
        real_coords = rp[:-1]
        r = self.manip_rotation_to_sample_rotation(rp[-1])
        xp, yp, zp = self.manip_frame.rotate_in_plane(
            real_coords, -rp[-1] * np.pi / 180.0, ax1=self.ax1, ax2=self.ax2
        )
        x, y, z = self.manip_frame.to_frame((xp, yp, zp), self.current_frame)
        return self.PseudoPosition(x, y, z, r)

    def move_sample(self, sample_id, **positions):
        if sample_id is not None:
            self.set_sample(sample_id)
        position = [p for p in self.default_coords]
        if "x" in positions:
            position[0] = positions["x"]
        if "y" in positions:
            position[1] = positions["y"]
        if "z" in positions:
            position[2] = positions["z"]
        if "r" in positions:
            position[3] = positions["r"]
        return self.move(position)

    def sample_rotation_to_manip_rotation(self, r):
        # Assumes that z-axis is the surface normal!!
        grazing = find_rotation(
            self.current_frame,
            (1, 0, 0),
            self.manip_frame,
            self.beam_direction,
            self.rotation_ax,
        )
        return grazing * 180.0 / np.pi + r

    def manip_rotation_to_sample_rotation(self, r):
        grazing = find_rotation(
            self.current_frame,
            (1, 0, 0),
            self.manip_frame,
            self.beam_direction,
            self.rotation_ax,
        )
        return r - grazing * 180.0 / np.pi
