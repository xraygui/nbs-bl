from abc import ABC, abstractmethod
import csv


class GeometryBase(ABC):
    def __init__(self):
        self.samples = {}
        self.sample_frames = {}
        self.current_sample = {}
        self.current_frame = None

    @abstractmethod
    def make_sample_frame(self, position):
        """
        Create a sample frame for the given position.

        Parameters
        ----------
        position : Any
            The position for which to create a sample frame.

        Returns
        -------
        Frame
            The created sample frame.
        """
        pass

    @abstractmethod
    def generate_geometry(self):
        """
        Generate the geometry for the holder.
        """
        pass

    @abstractmethod
    def get_geometry(self):
        """
        Get the geometry of the holder.

        Returns
        -------
        Any
            The geometry of the holder.
        """
        pass

    def attach_manipulator(self, manipframe):
        self.manip_frame = manipframe
        if self.current_frame is None:
            self.current_frame = self.manip_frame
        self.generate_geometry()

    def read_sample_file(self, filename):
        extension = filename.split(".")[-1]
        if extension in ["csv"] and hasattr(self, "read_sample_csv"):
            return self.read_sample_csv(filename)
        else:
            raise AttributeError(
                f"File had extension {extension}, but this geometry has no read method"
            )

    def add_sample(self, name, id, position, description="", origin="holder", **kwargs):
        """
        Add a sample to the geometry.

        Parameters
        ----------
        name : str
            Name of the sample
        id : str
            Unique identifier for the sample
        position : dict
            Position information for the sample
        description : str, optional
            Description of the sample
        origin : str, optional
            Origin of the sample position
        **kwargs : dict
            Additional sample metadata
        """
        if origin == "absolute":
            sample_frame = position
        else:
            sample_frame = self.make_sample_frame(position)

        self.samples[id] = {
            "name": name,
            "description": description,
            "position": position,
            "sample_id": id,
            "origin": origin,
            **kwargs,
        }
        self.sample_frames[id] = sample_frame

    def remove_sample(self, sample_id):
        """
        Remove a sample from the geometry.

        Parameters
        ----------
        sample_id : str
            ID of the sample to remove
        """
        self.samples.pop(sample_id, None)
        self.sample_frames.pop(sample_id, None)
        if self.current_sample.get("sample_id") == sample_id:
            self.current_sample.clear()
            self.current_frame = None

    def set_sample(self, sample_id):
        """
        Set the current sample.

        Parameters
        ----------
        sample_id : str
            ID of the sample to set as current
        """
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

    def clear_samples(self):
        """Clear all samples and frames."""
        self.samples.clear()
        self.sample_frames.clear()
        self.current_sample.clear()
        self.current_frame = None

    def get_sample_frame(self, sample_id):
        """
        Get the frame for a sample.

        Parameters
        ----------
        sample_id : str
            ID of the sample

        Returns
        -------
        Frame
            The sample's frame
        """
        return self.sample_frames.get(sample_id)

    def get_sample_metadata(self, sample_id):
        """
        Get metadata for a sample.

        Parameters
        ----------
        sample_id : str
            ID of the sample

        Returns
        -------
        dict
            The sample's metadata
        """
        return self.samples.get(sample_id)

    def get_current_frame(self):
        """
        Get the current frame.

        Returns
        -------
        Frame
            The current frame
        """
        return self.current_frame

    def get_current_sample(self):
        """
        Get the current sample metadata.

        Returns
        -------
        dict
            The current sample's metadata
        """
        return self.current_sample


class AbsoluteBar(GeometryBase):
    """
    This is a geometry that assumes that the position is absolute, and will never attempt
    to do any coordinate transformations.
    """

    def __init__(self):
        super().__init__()

    def make_sample_frame(self, position):
        """
        Always assume that the position is absolute, and return the coordinates
        """
        return position

    def generate_geometry(self):
        pass

    def get_geometry(self):
        side_md = {}
        side_frames = {}
        return side_md, side_frames


class Standard4SidedBar(GeometryBase):
    def __init__(self, width, length):
        super().__init__()
        self.length = length
        self.sides = 4
        self.width = width

    def make_sample_frame(self, position):
        side = position.get("side")
        # origin = position.get("origin", "bar")
        # if origin in ["abs", "absolute"]:
        #     x, y, z, r = position.get("coordinates")
        #     origin = (x, y, z)
        #     parent_frame = self.manip_frame.parent
        #     sample_frame = parent_frame.make_child_frame(origin=origin)

        # else:
        x1, y1, x2, y2 = position.get("coordinates")
        z = position.get("thickness", 0)
        origin = (0.5 * (x1 + x2), 0.5 * (y1 + y2), z)
        parent_frame = self.side_frames[int(side) - 1]
        sample_frame = parent_frame.make_child_frame(origin=origin)
        return sample_frame

    def generate_geometry(self):
        """Very brute force, could be refined to be more general"""
        axes = [(1, 0, 0), (0, 0, 1), (0, -1, 0)]
        origin = (0, 0, -1 * self.length)
        self.bar_frame = self.manip_frame.make_child_frame(*axes, origin=origin)
        side_axes = [
            [(0, 0, 1), (0, 1, 0), (-1, 0, 0)],
            [(-1, 0, 0), (0, 1, 0), (0, 0, -1)],
            [(0, 0, -1), (0, 1, 0), (1, 0, 0)],
            [(1, 0, 0), (0, 1, 0), (0, 0, 1)],
        ]
        hw = self.width / 2.0
        side_origins = [(-hw, 0, -hw), (hw, 0, -hw), (hw, 0, hw), (-hw, 0, hw)]
        self.side_frames = [
            self.bar_frame.make_child_frame(*axes, origin=origin)
            for axes, origin in zip(side_axes, side_origins)
        ]

    def get_geometry(self):
        # Implement the method here
        side_md = {}
        side_frames = {}
        for n in range(self.sides):
            side_frame = self.side_frames[n]
            side_str = f"side{n+1}"  # Humans one-index sides...
            side_dict = {
                "name": side_str,
                "id": side_str,
                "description": side_str,
                "position": [],
            }
            side_md[side_str] = side_dict
            side_frames[side_str] = side_frame
        return side_md, side_frames

    def read_sample_csv(self, filename):
        with open(filename, "r") as f:
            sampleReader = csv.reader(f, skipinitialspace=True)
            samplelist = [row for row in sampleReader]
            rownames = [n for n in samplelist[0] if n != ""]
            # rownames = ["sample_id", "sample_name", "side", "x1", "y1", "x2", "y2",
            #            "t", "tags"]
            samples = {}
            for sample in samplelist[1:]:
                sample_id = sample[0]
                sample_dict = {
                    key: sample[rownames.index(key)]
                    for key in rownames[1:]
                    if sample[rownames.index(key)] != ""
                }
                coordinates = (
                    float(sample_dict.pop("x1")),
                    float(sample_dict.pop("y1")),
                    float(sample_dict.pop("x2")),
                    float(sample_dict.pop("y2")),
                )
                thickness = sample_dict.pop("thickness", 0)
                side = sample_dict.pop("side")
                position = {
                    "side": side,
                    "coordinates": coordinates,
                    "thickness": thickness,
                }
                sample_dict["position"] = position
                samples[sample_id] = sample_dict
                if "sample_name" in sample_dict:
                    name = sample_dict.pop("sample_name")
                    sample_dict["name"] = name
        return samples


class Bar1d(GeometryBase):
    def __init__(self):
        super().__init__()

    def generate_geometry(self):
        pass

    def get_geometry(self):
        side_md = {}
        side_frames = {}
        return side_md, side_frames

    def make_sample_frame(self, position):
        x = position.get("coordinates")
        child_frame = self.manip_frame.make_child_frame(origin=x)
        return child_frame
