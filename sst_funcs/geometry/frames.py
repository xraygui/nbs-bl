import numpy as np
from .linalg import (vec, constructBasis, changeBasisMatrix, rad_to_deg,
                     deg_to_rad, rotz, rotzMat)
from .polygons import isInPoly, getMinDist


class NullFrame:
    def frame_to_beam(self, *args, **kwargs):
        return args

    def beam_to_frame(self, *args, **kwargs):
        return args

    def distance_to_beam(self, *args):
        v = np.array(args)
        return np.sqrt(np.dot(v, v))


class Axis:
    def __init__(self, x0, scale=1, parent=None):
        self.reset(x0, scale, parent=parent)

    def reset(self, x0, scale, parent=None):
        self.x0 = x0
        self.scale = scale
        self.parent = parent

    def update_basis(self, x):
        self.x0 = x

    def frame_to_parent(self, x):
        return x*self.scale + self.x0

    def parent_to_frame(self, x):
        return x*self.scale - self.x0

    def add_parent_frame(self, parent):
        """
        Adds a new parent at the top of the parent
        hierarchy, replacing the old global frame.
        Maybe dangerous in practice...
        """
        if self.parent is None:
            self.parent = parent
        else:
            self.parent.add_parent_frame(parent)

    def frame_to_global(self, x_frame):
        x_parent = self.frame_to_parent(x_frame)
        if self.parent is not None:
            return self.parent.frame_to_global(x_parent)
        else:
            return x_parent

    def global_to_frame(self, x_global):
        if self.parent is None:
            return self.parent_to_frame(x_global)
        else:
            x_parent = self.parent.global_to_frame(x_global)
            return self.parent_to_frame(x_parent)

    def frame_to_beam(self, x_frame):
        return self.frame_to_global(x_frame)

    def beam_to_frame(self, x_global):
        return self.global_to_frame(x_global)

    def distance_to_beam(self, x_beam_global):
        """
        Distance from beam to origin

        Parameters
        -----------
        x_beam_global : float
            beam position in global coordinate system
        """
        x = self.global_to_frame(x_beam_global)
        return x


class Interval(Axis):
    def __init__(self, x0, length, *args, parent=None):
        self.length = length
        super().__init__(x0, *args, parent=parent)

    def frame_to_global(self, x, origin="edge"):
        if origin == "center":
            x += self.length/2.0
        return super().frame_to_global(x)

    def global_to_frame(self, x, origin="edge"):
        x = super().global_to_frame(x)
        if origin == "center":
            x -= self.length/2.0
        return x

    def frame_to_beam(self, x_frame, **kwargs):
        return self.frame_to_global(x_frame, **kwargs)

    def beam_to_frame(self, x_global, **kwargs):
        return self.global_to_frame(x_global, **kwargs)

    def distance_to_beam(self, x_beam_global):
        x = self.global_to_frame(x_beam_global)
        d1 = np.abs(x)
        d2 = np.abs(x - self.length)
        if (d1 < self.length) and (d2 < self.length):
            return -1*min(d1, d2)
        else:
            return min(d1, d2)

    def make_sample_frame(self, position, t=0):
        x1, x2 = position
        frame = Interval(x1, x2 - x1, parent=self)
        return frame


class Frame:
    """
    20220117: This entire thing is too complicated. Having a "manip" argument
    was a really bad idea. I should have used a moveable manipulator frame
    instead. Indeed, this is what I have essentially done, but the complexity
    remains. There are also too many X_to_frame and frame_to_X functions.
    There should have only been "parent_to_frame" and "global_to_frame". No
    time to fix this now. Interval/Axis are done better
    """
    def __init__(self, p1, p2, p3, parent=None, rot_meas_axis=2):
        """
        Parameters
        ------------
        p1 : vector
            origin of the frame in the parent system
        p2 : vector
            defines the frame's y basis vector
        p3 : vector
            defines the plane of the x basis vector
        parent : Frame, optional
        rot_meas_axis : int
            Which axis will be used to measure rotation relative to the
            global coordinate system X-Y plane
        """
        self.rot_meas_axis = rot_meas_axis
        self.reset(p1, p2, p3, parent=parent)

    def reset(self, p1, p2, p3, parent=None):
        self.parent = parent
        self.update_basis(p1, p2, p3)
        self.update_rotation()

    def update_basis(self, p1, p2, p3):
        self.vectors = [p1, p2, p3]
        self.p0 = p1
        self._basis = constructBasis(p1, p2, p3)
        # r_offset
        self.A = changeBasisMatrix(*self._basis)
        self.Ainv = self.A.T

    def update_rotation(self):
        self.r0 = rad_to_deg(self._roffset())

    def add_parent_frame(self, parent):
        """
        Adds a new parent at the top of the parent
        hierarchy, replacing the old global frame.
        """
        if self.parent is None:
            self.parent = parent
        else:
            self.parent.add_parent_frame(parent)
        self.update_rotation()

    def reset_z(self, z, parent=None):
        self.p0[2] = z

    def _roffset(self):
        """
        R offset relative to the GLOBAL frame (not the parent frame!)

        Important note! It is a BAKED IN ASSUMPTION that
        these frames are being used for beamline samples, and
        that there is only one rotation axis.
        "Rotation" means the angle that the rotation axis makes
        with respect to the beam in the global x-y plane. This
        makes sense because we only have a 4-axis manipulator.
        If we had, god forbid, a 6-axis manipulator, none of this
        1-axis rotation stuff would make sense, and you would just
        have to specify an exact vector, rather than an angle.
        """

        # we bootstrap the rotation by finding the z-vector in the global
        # frame, even if
        # we have a parent.
        axis = vec(0, 0, 0)
        axis[self.rot_meas_axis] = 1
        n3 = (self.frame_to_global(axis, rotation='global') -
              self.frame_to_global(vec(0, 0, 0), rotation='global'))
        x = n3[0]
        y = n3[1]
        if y == 0:
            return 0
        elif x >= 0 and y >= 0:
            quad = 1
        elif x < 0 and y >= 0:
            quad = 2
        elif x <= 0 and y < 0:
            quad = 3
        else:
            quad = 4
        theta = np.arctan(y/x)
        if quad == 1:
            return theta
        elif quad == 2 or quad == 3:
            return theta + np.pi
        elif quad == 4:
            return theta + 2*np.pi

    def _to_global(self, v):
        return np.dot(self.A, v) + self.p0

    def _to_frame(self, v):
        return np.dot(self.Ainv, v - self.p0)

    def _manip_to_global(self, v_manip, manip, r):
        theta = deg_to_rad(r)
        v_global = rotz(theta, v_manip) + manip
        return v_global

    def _global_to_manip(self, v_global, manip, r):
        theta = deg_to_rad(r)
        v_manip = rotz(-theta, v_global - manip)
        return v_manip

    def frame_to_global(self, v_frame, manip=vec(0, 0, 0), r=0,
                        rotation="frame"):
        """
        Find the global coordinates of a point in the frame, given the
        rotation of the frame, and the manipulator position

        Parameters
        ------------
        v_frame : vector
            Coordinates of a point in the frame system
        manip : vector
            Manipulator coordinates
        r : float, degrees
            rotation of the frame
            (0 = grazing incidence, 90 = normal)
        """
        if rotation == 'frame':
            rg = r - self.r0
        else:
            rg = r
        v_global = self._to_global(v_frame)
        if self.parent is not None:
            return self.parent.frame_to_global(v_global, manip, r=rg,
                                               rotation='global')
        else:
            v_global = self._manip_to_global(v_global, manip, rg)
        return v_global

    def global_to_frame(self, v_global, manip=vec(0, 0, 0), r=0):
        """
        Find the frame coordinates of a point in the global system,
        given the manipulator position and rotation

        Parameters
        -----------
        v_global : vector
            global vector
        manip : vector
            current position of manipulator
        r : float, degrees
            rotation of the manipulator
        """
        if self.parent is not None:
            v_manip = self.parent.global_to_frame(v_global, manip, r)
        else:
            v_manip = self._global_to_manip(v_global, manip, r)
        v_frame = self._to_frame(v_manip)
        return v_frame

    def frame_to_beam(self, fx, fy, fz, fr=0, **kwargs):
        """
        Given a frame coordinate, and rotation, find the manipulator position
        and rotation that places the frame coordinate in the beam path.
        The beam position is assumed to be the origin of the global coordinate
        system.

        Returns
        --------
        coordinates : tuple
            The x, y, z, r coordinates of the manipulator that put the
            frame coordinate into the beam path
        """

        v_frame = vec(fx, fy, fz)
        v_global = -1*self.frame_to_global(v_frame, r=fr)
        gr = fr - self.r0
        gx, gy, gz = (v_global[0], v_global[1], v_global[2])
        return gx, gy, gz, gr

    def beam_to_frame(self, gx, gy, gz, gr=0, **kwargs):
        """
        Given a manipulator coordinate and rotation, find the beam intersection
        position and incidence angle in the frame coordinates. The beam
        position is assumed to be the origin of the global coordinate system.

        Parameters
        ------------
        gx : float
            manipulator x coordinate
        gy : float
            manipulator y coordinate
        gz : float
            manipulator z coordinate
        gr : float, degrees
            manipulator r coordinate

        Returns
        --------
        coordinates : tuple
            The x, y, z, r coordinates of the beam in the frame system
        """
        manip = vec(gx, gy, gz)
        v_frame = self.origin_to_frame(manip, gr)
        fx, fy, fz = (v_frame[0], v_frame[1], v_frame[2])
        fr = gr + self.r0
        return fx, fy, fz, fr

    def origin_to_frame(self, manip=vec(0, 0, 0), r=0):
        return self.global_to_frame(vec(0, 0, 0), manip, r)

    def project_beam_to_frame_xy(self, manip=vec(0, 0, 0), r=0):
        op = self.origin_to_frame(manip, r)
        theta = deg_to_rad(r)
        Rz_inv = rotzMat(-theta)
        vp = np.dot(self.Ainv, np.dot(Rz_inv, vec(0, 1, 0)))
        a = op[-1]/vp[-1]
        proj = op - a*vp
        return proj

    def distance_to_beam(self, gx, gy, gz, gr=0):
        """
        Given the manipulator coordinate (and rotation, for consistency),
        find the distance from the beam to the coordinate origin, ignoring
        the beam y-axis

        Parameters
        ------------
        gx : float
            manipulator x coordinate
        gy : float
            manipulator y coordinate
        gz : float
            manipulator z coordinate
        gr : float, degrees
            manipulator r coordinate

        Returns
        --------
        distance : float
            Distance from the global y-axis (the beam) to the coordinate origin
        """
        op = self.frame_to_global(vec(0, 0, 0), manip=vec(gx, gy, gz), r=gr)
        distance = np.sqrt(op[0]**2 + op[2]**2)
        return distance


class Panel(Frame):
    """
    A frame that has boundaries, making it a rectangle

    Parameters
    ------------
    p1 : vector
        origin of the frame in the parent system
    p2 : vector
        defines the frame's y basis vector
    p3 : vector
        defines the plane of the x basis vector
    parent : Frame, optional

    """
    def __init__(self, *args, width=19.5, height=130, parent=None):
        super().__init__(*args, parent=parent)
        self.width = width
        self.height = height
        self.edges = [vec(0, 0, 0), vec(width, 0, 0), vec(width, height, 0),
                      vec(0, height, 0)]

    def frame_to_beam(self, fx, fy, fz, fr=0, origin="edge"):
        if origin == "center":
            fx += self.width/2.0
            fy += self.height/2.0
        return super().frame_to_beam(fx, fy, fz, fr)

    def beam_to_frame(self, gx, gy, gz, gr=0, origin="edge"):
        fx, fy, fz, fr = super().beam_to_frame(gx, gy, gz, gr)
        if origin == "center":
            fx -= self.width/2.0
            fy -= self.height/2.0
        return fx, fy, fz, fr

    def real_edges(self, manip, r_manip):
        """
        Finds the vertices of the panel in global coordinate system,
        given the manipulator position

        Parameters
        -----------
        manip : vector
            Manipulator x,y,z position vector
        r_manip : float
            Manipulator rotation in degrees

        Returns
        --------
        Vertex positions in the global frame
        """
        re = []
        for edge in self.edges:
            real_coord = self.frame_to_global(edge, manip, r_manip,
                                              rotation='global')
            re.append(real_coord)
        return re

    def project_real_edges(self, manip, r_manip):
        """

        Parameters
        ------------
        manip : vector
            Manipulator x,y,z position vector
        r_manip : float
            Manipulator rotation in degrees

        Returns
        --------
        Vertex coordinates projected into the x-z axis
        """

        re = self.real_edges(manip, r_manip)
        ret = []
        for edge in re:
            ret.append(np.array([edge[0], edge[2]]))
        return ret

    def distance_to_beam(self, x, y, z, r):
        """
        Returns the distance from the beam to the closest edge of
        the Panel, given a manipulator position of x, y, z, r

        Parameters
        -------------
        x : float
            manipulator x coordinate
        y : float
            manipulator y coordinate
        z : float
            manipulator z coordinate
        r : float
            manipulator r coordinate (in degrees)

        Returns
        ----------
        distance : float
            The sign of distance is negative if the beam is inside the Panel,
            and positive if the beam is outside the Panel
        """

        manip = vec(x, y, z)
        real_edges = self.project_real_edges(manip, r)
        inPoly = isInPoly(vec(0, 0), *real_edges)
        distance = getMinDist(vec(0, 0), *real_edges)
        if inPoly:
            return -1*distance
        else:
            return distance

    def make_sample_frame(self, position, t=0):
        if len(position) == 4:
            x1, y1, x2, y2 = position
            p1 = vec(x1, y1, t)
            p2 = vec(x1, y2, t)
            p3 = vec(x2, y1, t)
            width = x2 - x1
            height = y2 - y1

            frame = Panel(p1, p2, p3, height=height, width=width,
                          parent=self)
            return frame


def make_geometry(*args, **kwargs):
    if len(args) == 3:
        if "height" in kwargs and "width" in kwargs:
            return Panel(*args, **kwargs)
        else:
            return Frame(*args, **kwargs)
