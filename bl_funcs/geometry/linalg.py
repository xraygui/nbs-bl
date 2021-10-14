import numpy as np

"""
Module that implements basic linear algebra as it relates to vectors and
basis transformation/construction
"""


def vec(*args):
    """
    Construct a vector from components
    """
    return np.array(args)


def normVector(v):
    """
    Return the unit vector of v
    """
    n = np.sqrt(np.dot(v, v))
    return v/n


def vec_len(v):
    """
    Find the magnitude of vector v
    """
    return np.sqrt(np.dot(v, v))


def vec_angle(v1, v2):
    """
    Find the angle between v1 and v2
    """
    return np.arccos(np.dot(v1, v2)/(vec_len(v1)*vec_len(v2)))


def findOrthonormal(v1, v2):
    """
    Find the length 1 vector normal to v1 and v2
    """
    v3 = np.cross(v1, v2)
    return normVector(v3)


def constructBasis(p1, p2, p3):
    """
    Construct a basis from three points

    Parameters
    ------------
    p1 : vector
        The origin of the vector space
    p2 : vector
        defines the y basis vector
    p3 : vector
        defines the plane of the x basis vector

    Returns
    ----------
    Returns three vectors, n1, n2, and n3, that form a basis.
    n2 : vector
        the "y" vector, is defined by p2 - p1
    n3 : vector
        the "z" vector, is defined as being orthornormal to n2 and p3-p1,
    n1 : vector
        the "x" vector, is then uniquely defined as orthonormal to n2 and n3
    """
    v1 = p3 - p1
    v2 = p2 - p1
    n2 = normVector(v2)
    n3 = findOrthonormal(v1, n2)
    n1 = findOrthonormal(n2, n3)
    return n1, n2, n3


def changeBasisMatrix(n1, n2, n3):
    return np.vstack([n1, n2, n3]).T


def constructBorders(p1, p2, p3, sidelength=1):
    n1, n2, n3 = constructBasis(p1, p2, p3)
    origin = p1
    origin2 = n1*sidelength + origin
    borders = {'n1': n1, 'n2': n2,
               'o1': origin, 'o2': origin2}
    return borders


def rotzMat(theta):
    """
    Parameters
    -----------
    theta : float, radians
    """
    return np.array([[np.cos(theta), -np.sin(theta), 0],
                     [np.sin(theta),  np.cos(theta), 0],
                     [0, 0, 1]])


def rotz(theta, v):
    """
    Rotate a vector by theta around the z axis
    """
    rz = rotzMat(theta)
    return np.dot(rz, v)


def deg_to_rad(d):
    return d*np.pi/180.0


def rad_to_deg(d):
    return d*180.0/np.pi
