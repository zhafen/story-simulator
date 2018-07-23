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

class World( object ):

    @utilities.store_parameters
    def __init__(
        self,
        world_dir,
    ):
        pass

    ########################################################################
    # Properties
    ########################################################################

    def generic_excel_getter( self, property_name, subfolders=[] ):
        '''Generic property for loading in an excel file in a subdirectory.'''

        hidden_attr = '_{}'.format( property_name )

        if not hasattr( self, hidden_attr ):

            # Set up the subfolders
            used_subfolders = copy.copy( subfolders )
            used_subfolders.append( '{}.xlsx'.format( property_name ) )

            filepath = os.path.join( self.world_dir, *used_subfolders )

            setattr( self, hidden_attr, pd.read_excel( filepath ) )

        return getattr( self, hidden_attr )

    ########################################################################

    @property
    def historical_events( self ):

        return self.generic_excel_getter( 'historical_events', [ 'world' ] )

    ########################################################################

    @property
    def events( self ):

        return self.generic_excel_getter( 'events', [ 'world' ] )

    ########################################################################

    @property
    def characters( self ):

        return self.generic_excel_getter( 'characters', [ 'world/characters' ] )

    ########################################################################

    @property
    def nodes( self ):

        return self.generic_excel_getter( 'nodes', [ 'world/settings' ] )

    ########################################################################
    # Methods
    ########################################################################

    def sample_part( self, part_name, n_samples=1 ):

        part = getattr( self, part_name )

        ind = prob_tools.sample_discrete_probabilities( part['Likelihood'].values, normalize=True )

        if n_samples == 1:
            return part.loc[ind]
        else:
            raise Exception( "Multiple samples not implemented yet." )
