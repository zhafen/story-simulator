#!/usr/bin/env python
'''Functions for generating names.

@author: Zach Hafen
@contact: zachary.h.hafen@gmail.com
@status: Development
'''

import numpy as np

import matplotlib.colors

import story_simulator.utils.utils as utils

########################################################################
########################################################################

def generate_color( request_user_input=True ):
    '''Generate a random color.'''

    color = np.random.random( 3 )

    if not request_user_input:
        return color

    accept_color = False
    while not accept_color:

        print( 'HSV = {}'.format( matplotlib.colors.rgb_to_hsv( color ) ) )

        utils.show_color( color )

        user_input = input( 'Accept color?' ) 

        accept_color = user_input == 'y'

        if accept_color:
            continue

        # If trying to tweak the color
        arg, value = user_input.split( ' = ' )
        if arg in tweak_color.__code__.co_varnames:
            color = tweak_color( color, **{ arg: float( value )} )

    return color

########################################################################

def tweak_color(
    c,
    dh = None,
    ds = None,
    dv = None,
    h = None,
    s = None,
    v = None,
):
    '''Change the values in a color.'''

    c_hsv = np.array( matplotlib.colors.rgb_to_hsv( c ) )

    # Shift the color slightly
    if dh is not None:
        c_hsv[0] += dh
        if c_hsv[0] > 1.:
            c_hsv[0] -= 1.
        if c_hsv[0] < 0.:
            c_hsv[0] += 1.
    if ds is not None:
        c_hsv[1] += ds
    if dv is not None:
        c_hsv[2] += dv

    # Set the color
    if h is not None:
        c_hsv[0] = h
    if s is not None:
        c_hsv[1] = s
    if v is not None:
        c_hsv[2] = v

    c = matplotlib.colors.hsv_to_rgb( c_hsv )

    print( 'HSV = {}'.format( matplotlib.colors.rgb_to_hsv( c ) ) )

    utils.show_color( c )

    return c
