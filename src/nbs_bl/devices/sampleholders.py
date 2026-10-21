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

        # Request status containers from global manager
        self.samples = {}
        # GLOBAL_USER_STATUS.request_status_dict(
        #     f"{self.name.upper()}_SAMPLES", use_redis=use_redis
        # )
        # current_sample contains metadata, can use Redis
        self.current_sample = {}
        # GLOBAL_USER_STATUS.request_status_dict(
        #     f"{self.name.upper()}_CURRENT", use_redis=use_redis
        # )

        self.sample_frames = {}
        self.holder_md = {}
        self.holder_frames = {}
        self.current_frame = self.attachment_frame
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
        self.samples.clear()
        self.sample_frames.clear()
        self.current_sample.clear()

    def clear_samples(self):
        self.samples.clear()
        self.sample_frames.clear()
        self.current_sample.clear()

    def add_sample(self, name, id, position, description="", origin="holder", **kwargs):
        if origin == "absolute":
            sample_frame = position
        else:
            sample_frame = self.holder.make_sample_frame(position)

        self.samples[id] = {
            "name": name,
            "description": description,
            "position": position,
            "sample_id": id,
            "origin": origin,
            **kwargs,
        }
        self.sample_frames[id] = sample_frame

    def shift_sample(self, sample_id, dx=0, dy=0, dz=0):
        """
        Correct a sample's stored position by (dx, dy, dz) in its own frame.

        Use this when a measurement (e.g. an edge scan) shows a sample is not
        where the sample file says. For a bar, x is along the surface, y is
        along the bar, and z is the surface normal (the thickness).

        Parameters
        ----------
        sample_id : str
            The sample to correct.
        dx, dy, dz : float
            How far the sample really is from its stored position, in mm.
        """
        sample = copy.deepcopy(self.samples[sample_id])
        position = sample["position"]
        if sample.get("origin") == "absolute":
            coordinates = list(position["coordinates"])
            for i, d in enumerate((dx, dy, dz)[: len(coordinates)]):
                coordinates[i] += d
            position = {**position, "coordinates": coordinates}
            frame = position
        else:
            position = self.holder.shift_position(position, dx=dx, dy=dy, dz=dz)
            frame = self.holder.make_sample_frame(position)
        sample["position"] = position
        # Assign the whole entry so Redis-backed sample dicts save it.
        self.samples[sample_id] = sample
        self.sample_frames[sample_id] = frame
        if self.current_sample.get("sample_id") == sample_id:
            self.set_sample(sample_id)

    def remove_sample(self, sample_id):
        self.samples.pop(sample_id, None)
        self.sample_frames.pop(sample_id, None)
        if self.current_sample.get("sample_id") == sample_id:
            self.current_sample.clear()

    def set_sample(self, sample_id):
        if sample_id in self.sample_frames:
            self.current_frame = self.sample_frames[sample_id]
            self.current_sample.clear()
            self.current_sample.update(self.samples[sample_id])
        elif sample_id in self.holder_frames:
            self.current_frame = self.holder_frames[sample_id]
            self.current_sample.clear()
            self.current_sample.update(self.holder_md[sample_id])
        else:
            raise KeyError(
                f"Sample ID {sample_id} not found in sample frames or holder frames"
            )

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
            # add_sample_to_globals(
            #     sample_id, name, position, side, thickness, description, **sdict
            # )
            self.add_sample(
                name,
                sample_id,
                position,
                description=description,
                **sdict,
            )
        return

    def load_sample_file(self, filename, clear=True):
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
        self.sample_frames.clear()
        for sample_id, sample in self.samples.items():
            if self.holder is None and sample["origin"] != "absolute":
                continue

            if sample["origin"] == "absolute":
                self.sample_frames[sample_id] = sample["position"]
            else:
                self.sample_frames[sample_id] = self.holder.make_sample_frame(
                    sample["position"]
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
        if isinstance(self.current_frame, Frame):
            # If current_frame is a Frame object, use the existing conversion
            (position,) = self.current_frame.to_frame(pp, self.manip_frame)
        else:
            # If current_frame is a coordinate dict, add its value to pp
            frame_coords = self.current_frame.get("coordinates", [0])
            position = pp.sx + frame_coords[0]

        return self.RealPosition(position)

    @real_position_argument
    def inverse(self, rp):
        if isinstance(self.current_frame, Frame):
            # If current_frame is a Frame object, use the existing conversion
            (position,) = self.manip_frame.to_frame(rp, self.current_frame)
        else:
            # If current_frame is a coordinate dict, subtract its value from rp
            frame_coords = self.current_frame.get("coordinates", [0])
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
        # Where the rotation axis crosses the beam, in motor coordinates.
        # Only the two components perpendicular to the rotation axis are used.
        self.rotation_center = np.zeros(3)

    def set_rotation_center(self, *center):
        """
        Set the motor position (x, y, z) at which the rotation axis is in the beam.

        Only the components perpendicular to the rotation axis matter. Sample
        positions at r=0 don't change; rotations now pivot about this point.
        """
        c = np.zeros(3)
        c[: len(center)] = center
        c[self.rotation_ax] = 0
        self.rotation_center = c

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

        if isinstance(self.current_frame, Frame):
            # If current_frame is a Frame object, use the existing conversion
            xp, yp, zp = self.current_frame.to_frame(
                sample_coords,
                self.manip_frame,
            )

            r = self.sample_rotation_to_manip_rotation(r)
            c = self.rotation_center
            x, y, z = (
                self.manip_frame.rotate_in_plane(
                    np.array((xp, yp, zp)) - c,
                    r * np.pi / 180.0,
                    ax1=self.ax1,
                    ax2=self.ax2,
                )
                + c
            )
        else:
            # If current_frame is a coordinate dict, add its values to sample_coords
            frame_coords = self.current_frame.get("coordinates", [0, 0, 0, 0])
            x = sample_coords[0] + frame_coords[0]
            y = sample_coords[1] + frame_coords[1]
            z = sample_coords[2] + frame_coords[2]
            r += frame_coords[3]

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

        if isinstance(self.current_frame, Frame):
            r = self.manip_rotation_to_sample_rotation(rp[-1])
            c = self.rotation_center
            xp, yp, zp = (
                self.manip_frame.rotate_in_plane(
                    np.array(real_coords) - c,
                    -rp[-1] * np.pi / 180.0,
                    ax1=self.ax1,
                    ax2=self.ax2,
                )
                + c
            )
            # If current_frame is a Frame object, use the existing conversion
            x, y, z = self.manip_frame.to_frame((xp, yp, zp), self.current_frame)
        else:
            # If current_frame is a coordinate dict, subtract its values from xp, yp, zp, r
            frame_coords = self.current_frame.get("coordinates", [0, 0, 0, 0])
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
        if isinstance(self.current_frame, Frame):
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

    def recenter_sample_here(self, sample_id=None):
        """
        Make the current beam position the center of a sample.

        Move the beam onto the true sample center (e.g. found by an edge
        scan) first. The sample's stored position is shifted by the current
        sx, sy offset, so afterwards this spot reads sx = sy = 0.

        Parameters
        ----------
        sample_id : str, optional
            The sample to correct. Defaults to the current sample.
        """
        if sample_id is None:
            sample_id = self.current_sample.get("sample_id")
        if sample_id not in self.samples:
            raise KeyError(f"Sample ID {sample_id} not found in samples")
        previous = self.current_sample.get("sample_id")
        self.set_sample(sample_id)
        sx, sy, _, _ = (float(v) for v in self.inverse(self.real_position))
        self.shift_sample(sample_id, dx=sx, dy=sy)
        if previous is not None and previous != sample_id:
            self.set_sample(previous)
        return sx, sy

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


def manipulatorFactory4Ax(xPV, yPV, zPV, rPV):
    class Manipulator(Manipulator4AxBase):
        x = Cpt(FlyableMotor, xPV, name="x", kind="hinted")
        y = Cpt(FlyableMotor, yPV, name="y", kind="hinted")
        z = Cpt(FlyableMotor, zPV, name="z", kind="hinted")
        r = Cpt(FlyableMotor, rPV, name="r", kind="hinted")

    return Manipulator
