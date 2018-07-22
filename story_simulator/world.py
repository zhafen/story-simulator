#!/usr/bin/env python
'''Objects and function for creating and dealing with characters.

@author: Zach Hafen
@contact: zachary.h.hafen@gmail.com
@status: Development
'''

import numpy as np
import os
import pandas as pd

import hoard.utils.utilities as utilities
import hoard.utils.probability_tools as prob_tools

########################################################################
########################################################################

class World( object ):

    @utilities.store_parameters
    def __init__(
        self,
        world_dir,
    ):
        pass

    ########################################################################

    @property
    def historical_events( self ):

        if not hasattr( self, '_historical_events' ):

            filepath = os.path.join( self.world_dir, 'world', 'historical_events.xlsx' )

            self._historical_events = pd.read_excel( filepath )

        return self._historical_events

    ########################################################################

    @property
    def events( self ):

        if not hasattr( self, '_events' ):

            filepath = os.path.join( self.world_dir, 'world', 'events.xlsx' )

            self._events = pd.read_excel( filepath )

        return self._events

    ########################################################################

    def sample_part( self, part_name, n_samples=1 ):

        part = getattr( self, part_name )

        ind = prob_tools.sample_discrete_probabilities( part['Likelihood'].values, normalize=True )

        if n_samples == 1:
            return part.loc[ind]
        else:
            raise Exception( "Multiple samples not implemented yet." )
