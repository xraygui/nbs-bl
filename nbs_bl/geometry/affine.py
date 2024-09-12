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

    def make_child_frame(self, *axes, origin=None):
        return Frame(*axes, origin=origin, parent=self)


class Frame:
    def __init__(self, *axes, origin=None, parent=None):
        if not axes and origin is None:
            raise ValueError("Either axes or origin must be provided")

        if origin is not None:
            self.origin = np.array(origin)
            self.dim = len(origin)

            if not axes:
                axes = [
                    tuple([1 if i == j else 0 for i in range(self.dim)])
                    for j in range(self.dim)
                ]

            self.axes = tuple(self._ensure_axis(ax) for ax in axes)
        else:
            self.axes = tuple(self._ensure_axis(ax) for ax in axes)
            self.dim = self.axes[0].dim
            self.origin = np.zeros(self.dim)

        if parent is not None:
            self.parent = parent
            if self.parent.dim != self.dim:
                raise ValueError("Frame must have same dimension as parent")
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

    @staticmethod
    def _ensure_axis(ax):
        """
        Convert coordinate tuple to Axis object if necessary.

        Parameters
        ----------
        ax : Axis or tuple
            The axis or coordinates to convert.

        Returns
        -------
        Axis
            An Axis object.
        """
        if isinstance(ax, Axis):
            return ax
        elif isinstance(ax, (tuple, list, np.ndarray)):
            return Axis.from_coords(*ax)
        else:
            raise ValueError(
                f"Invalid axis type: {type(ax)}. Expected Axis or coordinate tuple."
            )

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

    def make_child_frame(self, *axes, origin=None):
        return Frame(*axes, origin=origin, parent=self)

    def rotate_in_plane(self, coords, phi, ax1=0, ax2=1):
        """
        Rotates around z-axis by default
        """
        M = np.zeros((self.dim, self.dim))
        for i in range(self.dim):
            if i != ax1 and i != ax2:
                M[i, i] = 1
        M[ax1, ax1] = np.cos(phi)
        M[ax1, ax2] = -np.sin(phi)
        M[ax2, ax1] = np.sin(phi)
        M[ax2, ax2] = np.cos(phi)
        return np.dot(M, np.array(coords))


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


def angle_between_vectors_2d(v1, v2):
    """
    Calculate the angle between two 2D vectors in the x-y plane.

    Parameters:
    v1, v2 : array-like
        The two vectors to compare. Each should be a 2D vector [x, y].

    Returns:
    float
        The angle between the vectors in radians.
    """
    # Ensure the vectors are numpy arrays
    v1 = np.array(v1)
    v2 = np.array(v2)

    # Calculate the angle using atan2
    angle = np.arctan2(v2[1], v2[0]) - np.arctan2(v1[1], v1[0])

    # Normalize the angle to be between -pi and pi
    return angle % (2 * np.pi)


def find_rotation(child_frame, child_ax, parent_frame, parent_ax, around_ax=2):
    origin = child_frame.to_frame([0, 0, 0], parent_frame)
    vector = child_frame.to_frame(child_ax, parent_frame) - origin

    angle = angle_between_vectors_2d(
        np.delete(vector, around_ax), np.delete(parent_ax, around_ax)
    )
    return angle
