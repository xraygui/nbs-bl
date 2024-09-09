import numpy as np


class NullFrame:
    def __init__(self, dim):
        self.dim = dim
        self.origin = np.zeros(dim)

    def get_global(self):
        return self

    def to_global(self, coords):
        return coords

    def from_global(self, coords):
        return coords

    def make_child_frame(self, *axes, origin):
        return Frame(*axes, origin=origin, parent=self)


class Frame:
    def __init__(self, *axes, origin, parent=None):
        if not axes:
            raise ValueError("At least one axis must be provided")

        self.axes = tuple(axes)
        self.origin = np.array(origin)
        self.dim = self.axes[0].dim

        if parent is not None:
            self.parent = parent
            if self.parent.dim != self.dim:
                raise ValueError("Frame most have same dimension as parent")
        else:
            self.parent = NullFrame(self.dim)

        if len(self.origin) != self.dim:
            raise ValueError("Origin must have same dimension as axes")

        if any(axis.dim != self.dim for axis in self.axes):
            raise ValueError("All axes must have the same dimension")

        if len(self.axes) != self.dim:
            raise ValueError("Number of axes must equal the dimension of each axis")

        self.A = np.column_stack(
            [axis.coords for axis in self.axes] + [np.append(self.origin, 1)]
        )
        self.Ainv = np.linalg.inv(self.A)

    def get_global(self):
        return self.parent.get_global()

    def to_parent(self, coords):
        if len(coords) != self.dim:
            raise ValueError("Coordinates must have same Dimension as Frame")
        return np.dot(self.A, np.append(coords, 1))[:-1]

    def to_global(self, coords):
        if len(coords) != self.dim:
            raise ValueError("Coordinates must have same Dimension as Frame")
        return self.parent.to_global(self.to_parent(coords))

    def to_frame(self, coords, frame):
        if self.get_global() != frame.get_global():
            raise ValueError("Frames must have same global frame")
        global_coords = self.to_global(coords)
        return frame.from_global(global_coords)

    def from_parent(self, coords):
        """
        coords in parent frame
        """
        return np.dot(self.Ainv, np.append(coords, 1))[:-1]

    def from_global(self, coords):
        """
        coords in parent frame
        """
        parent_coords = self.parent.from_global(coords)
        return self.from_parent(parent_coords)

    def make_child_frame(self, *axes, origin):
        return Frame(*axes, origin=origin, parent=self)


class Axis:
    def __init__(self, *coords):
        self.coords = np.array(coords + (0,))
        self.dim = len(coords)

    @classmethod
    def from_coords(cls, *coords):
        """
        Create an Axis object from a list of coordinates, normalizing them.

        Parameters
        ----------
        coords : list or array-like
            The coordinates to create the Axis from.

        Returns
        -------
        Axis
            A new Axis object with normalized coordinates.

        """
        coords = np.array(coords)
        norm = np.linalg.norm(coords)
        if norm == 0:
            raise ValueError("Cannot create an Axis with zero-length vector")
        normalized_coords = coords / norm
        return cls(*normalized_coords)


def align_axes(child_frame, child_ax, parent_frame, parent_ax, around_ax=None):
    origin = child_frame.to_parent(child_frame.origin)
