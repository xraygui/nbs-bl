from abc import ABC, abstractmethod


class GeometryBase(ABC):
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
        self.generate_geometry()


class Standard4SidedBar(GeometryBase):
    def __init__(self, width, length):
        self.length = length
        self.sides = 4
        self.width = width

    def make_sample_frame(self, position):
        side = position.get("side")
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


class Bar1d(GeometryBase):
    def __init__(self):
        pass

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
