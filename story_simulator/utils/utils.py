#!/usr/bin/env python
'''Helper functions

@author: Zach Hafen
@contact: zachary.h.hafen@gmail.com
@status: Development
'''

import matplotlib.pyplot as plt
import matplotlib.patches

########################################################################
########################################################################

def show_color( c ):
    '''Display a block of color c.

    Args:
        c (color): Color to display.
    '''

    fig = plt.figure( figsize=(2,1) )
    ax = plt.gca()

    ax.add_patch( matplotlib.patches.Rectangle( (0, 0), 10, 10, color=c ) )

    ax.axis( 'off' )

    plt.show()
