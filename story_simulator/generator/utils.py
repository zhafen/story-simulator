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

def generate_color():

    accept_color = False
    while not accept_color:

        color = np.random.random( 3 )

        print( 'HSV = {}'.format( matplotlib.colors.rgb_to_hsv( color ) ) )

        utils.show_color( color )

        accept_color = input( 'Accept color?' ) == 'y'

    return color
