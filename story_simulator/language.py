#!/usr/bin/env python
'''Objects and function for creating and dealing with characters.

@author: Zach Hafen
@contact: zachary.h.hafen@gmail.com
@status: Development
'''

import copy
import numpy as np
import os
import pandas as pd

import hoard.utils.utilities as utilities
import hoard.utils.probability_tools as prob_tools

########################################################################
########################################################################

class Language( object ):

    @utilities.store_parameters
    def __init__(
        self,
        name,
        world,
    ):
        pass

    ########################################################################
    # Properties
    ########################################################################

    @property
    def attrs( self ):

        return world.languages[name]

    ########################################################################

    @property
    def data( self ):

        if not hasattr( self, '_data' ):

            filepath = os.path.join( self.world.world_dir, 'world', 'languages', '{}.hdf5'.format( self.name ) )
            self._data = h5py.File( filepath, 'a' )

        return self._data
