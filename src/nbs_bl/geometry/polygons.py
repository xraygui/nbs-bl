import numpy as np
from .linalg import vec_len

"""
Module that computes areas, distances, and inclusion in polygons
"""


def triarea(p1, p2, p3):
    n1 = p1 - p2
    n2 = p3 - p2
    return 0.5*(n1[0]*n2[1] - n1[1]*n2[0])


def getPointAreas(p, *args):
    areas = []
    for n in range(len(args)):
        areas.append(triarea(p, args[n-1], args[n]))
    return areas


def distFromTri(p, a, b):
    area = np.abs(triarea(p, a, b))
    d = vec_len(a - b)
    s1 = vec_len(a - p)
    s2 = vec_len(b - p)
    if np.isclose(d, 0):
        return min(s1, s2)
    elif s1**2 > d**2 + s2**2:
        return s2
    elif s2**2 > d**2 + s1**2:
        return s1
    else:
        return 2.0*area/d


def getMinDist(p, *args):
    distances = []
    for n in range(len(args)):
        distances.append(distFromTri(p, args[n-1], args[n]))
    return np.min(distances)


def prunePoints(*args):
    pruned = []
    for n in range(len(args)):
        if not np.all(np.isclose(args[n-1] - args[n], 0.0)):
            pruned.append(args[n])
    return pruned


def isInPoly(p, *args):
    # Works for convex polygons only!
    polyPoints = prunePoints(*args)
    areas = np.array(getPointAreas(p, *polyPoints))
    return (np.all(areas < 0) or np.all(areas > 0))
