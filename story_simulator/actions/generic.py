#!/usr/bin/env python
'''Generic actions available to characters

@author: Zach Hafen
@contact: zachary.h.hafen@gmail.com
@status: Development
'''

import numpy as np
import os
import pandas as pd
import unyt

import hoard.utils.utilities as utilities

########################################################################
########################################################################

class Walk( object ):

    @utilities.store_parameters
    def __init__(
        self,
        new_position,
        displacement,
        speed = 1.4,
    ):

        # Attach MKS units if not given
        if not isinstance( self.displacement, unyt.unyt_quantity ):
            self.displacement *= unyt.m
        if not isinstance( self.speed, unyt.unyt_quantity ):
            self.speed *= unyt.m / unyt.s

    ########################################################################

    def time_to_complete( self ):
        '''Determine how long the action will take to complete. This is a
        standard function for actions.

        Returns:
            float:
                The time to complete this action in seconds.
        '''

        t = self.displacement / self.speed

        return t.to( 's' ).value
