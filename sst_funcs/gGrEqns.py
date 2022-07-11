import numpy as np
import scipy.optimize as opt
import bluesky.plan_stubs as bps
from .printing import run_report

run_report(__file__)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
basic general equations applying to gratings and grating instruments
assumes all angular arguments are passed as degrees
assumes length units are in mm 
@author: dvorak
"""


def getBetaDeg(en_eV, alpha_deg, k_invmm, m):
    # calculate beta in deg
    # en_eV: energy units of electron Volts
    # alpha_deg: incident angle in degrees
    # k_invmm: central line density in mm^-1
    # m: diffraction order unitless integer
    hc = 0.0012398  # in units of eV mm
    lambda_mm = hc / en_eV  # wavelength in mm
    alpha = np.radians(alpha_deg)  # alpha angle in radians
    beta = np.arcsin((m * k_invmm * lambda_mm - np.sin(alpha)))  # beta angle in radians
    return np.degrees(beta)


def ruben2005eqn8m(en_eV, cff, k_invmm, m):
    #   eqn 8, doi:10.1016/j.nima.2004.09.007, to calculate alpha from cff
    #   generalized to include higher orders
    #   en_eV is the energy in electron volts
    #   cff is unitless constant of fixed focus
    #   k_invmm is central line density in mm-1
    #   m is the diffraction order, integer, unitless
    #   returns alpha in degrees
    #   works for grazing incidence, 2000 eV, 1800 mm-1, cff=2, m=+1 thru +5
    #   works for grazing incidence, 2000 eV, 1800 mm-1, cff=0.2, m=-1 thru -5
    aa = 1 / (cff ** 2 - 1)  ## unitless
    hc = 0.0012398  # in units of eV mm
    lambda_mm = hc / en_eV  ## in mm
    return np.degrees(np.arcsin(-m * k_invmm * lambda_mm * aa + np.sqrt(1 + (cff * m * k_invmm * lambda_mm * aa) ** 2)))


def get_mirror_grating_angles(en_eV, cff, k_invmm, m):
    a = ruben2005eqn8m(en_eV, cff, k_invmm, m)  # twice the angle between mirror and grating in equation land
    b = getBetaDeg(en_eV, a, k_invmm, m)  # angle of pre-mirror (in degrees) in equation land
    mirror_angle = -(180 - a + b) / 2  # tangle of the mirror pitch for the actual motor (degrees)
    grating_angle = -90 - b  # angle of the grating pitch for the actual motor (degrees)
    return [mirror_angle, grating_angle]


def energy(mirror,grating, k_invmm, m):
    hc = 0.0012398  # in units of eV mm
    b = np.radians(-90 - grating)
    a = np.radians(2 * mirror + 90 - grating)
    return hc * k_invmm * m / (np.sin(a) + np.sin(b))


def find_best_offsets(mirror_pitches, grating_pitches, mguesses, eVs, k_invmm):
    '''
    given a bunch of measurements of mirror and grating pitches, fits the most likely constant offsets
    for the mirror and grating pitch.  Each measurement can be at a different order(m) and a different energy
    the grating parameters should not change, so only the constant line density is needed

    mirror_pitches : list or array of length n
        experimental mirror pitch angles

    grating_pitches : list or array of length n
        experimental grating pitch angles

    m_guesses : list or array of length n
        the diffraction order which was scanned

    eVs : list or array of length n
        the energy of each measurement (allows for different calibrants)

    k_invmm : single number the central spacing of the grating in mm^-1

    output: the result of numpy.optimize = has a lot of components which might be useful, the most obvious of which are
        output.x the optimized offsets of the mirror, and grating pitch
        output.success wether the optimize function thinks that it succeeded or not.  experince shows that good fits are still possible when this is false
    '''
    fit_result = opt.minimize(diffraction_pitch_offset_error_func,
                              x0=[0.0001, -0.0001],
                              args=(
                                  mirror_pitches,
                                  grating_pitches,
                                  mguesses,
                                  eVs,
                                  k_invmm
                              )
                              )
    return fit_result



def diffraction_pitch_offset_error_func(
        fit_elements,
        mirror_pitches,
        grating_pitches,
        m_guesses,
        en_eVs,
        k_invmm):
    '''
    fit_elements, an 2 element array:
        mirror angle offset,
        grating angle offset

    mirror_pitches : list or array of length n
        experimental mirror pitch angles

    grating_pitches : list or array of length n
        experimental grating pitch angles

    m_guesses : list or array of length n
        the diffraction order which was scanned

    en_eV : list or array of length n
        the energy of each measurement (allows for different calibrants)

    k_invmm : single number the central spacing of the grating in mm^-1
    '''
    error = 0
    for mp, gp, m, en_eV in zip(mirror_pitches, grating_pitches, m_guesses, en_eVs):
        mir = mp - fit_elements[0]  # the test mirror position
        grat = gp - fit_elements[1]  # the test grating position
        en_theoretical = energy(mir,grat, k_invmm, m)  # what energy these test positions would produce
        error += (en_theoretical - en_eV) ** 2
    return error


def set_pgm_offsets(error_object, energy_object):
    yield from bps.mvr(energy_object.monoen.mirror2.user_offset,-error_object.x[0]) # right now we have to set the negative of the fit value as the delta in the offset
    yield from bps.mvr(energy_object.monoen.grating.user_offset,-error_object.x[1])


def test_grating_fit(numpoints, minc, maxc, minm, maxm, energy, k, noise, moffset, goffset):
    # create some fake measurements of grating and mirror positions to test the fit function

    cs = np.linspace(minc, maxc, numpoints)  # used to generate test pairs of pitches
    ms = np.round(np.linspace(minm, maxm, numpoints))
    evs = np.ones(numpoints) * energy
    merr = np.random.normal(0, noise, numpoints)
    gerr = np.random.normal(0, noise, numpoints)

    mirrors, gratings = list(zip(*[get_mirror_grating_angles(energy, c, k, m) for c, m in zip(cs, ms)]))
    mirrors += merr + moffset
    gratings += gerr + goffset
    return find_best_offsets(mirrors, gratings, ms, evs, k)




'''
mirror positions: [-3.6558274763042604, -3.3921585294849734, -3.1876054822737245, -3.0234213066329048, -2.8882065368134207, -2.774584471608641, -2.6775464182938222, -2.5935586706589646]
grating positions: [-4.107032615400001, -3.880574386500001, -3.709388039800004, -3.5753463783000043, -3.4671052284000012, -3.379157631200002, -3.3047008284000015, -3.242455403500003]
energy positions: [291.65, 291.65, 291.65, 291.65, 291.65, 291.65, 291.65, 291.65]
orders: [1, 1, 1, 1, 1, 1, 1, 1]


mirror positions: [-3.234388850111962, -3.0810948898872326, -2.9527235798924423, -4.572999932948626, -4.3563799893796045, -4.1749665476012225]                                             
grating positions: [-3.7760457088000052, -3.6498169308000072, -3.546186037900007, -5.3394722246000015, -5.160893796100005, -5.014527626700001]
energy positions: [291.65, 291.65, 291.65, 291.65, 291.65, 291.65]
orders: [1, 1, 1, 2, 2, 2]

'''