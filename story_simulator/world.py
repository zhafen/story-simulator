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

    @property
    def historical_events( self ):

        return utilities.generic_table_getter(
            self,
            'historical_events',
            self.world_dir,
            subfolders = [ 'world' ]
        )

    ########################################################################

    @property
    def events( self ):

        return utilities.generic_table_getter(
            self,
            'events',
            self.world_dir,
            subfolders = [ 'world' ]
        )

    ########################################################################

    @property
    def languages( self ):

        return utilities.generic_table_getter(
            self,
            'languages',
            self.world_dir,
            subfolders = [ 'world', 'languages' ]
        )

    @languages.setter
    def languages( self, value ):
        utilities.generic_table_setter(
            self,
            'languages',
            value,
            self.world_dir,
            subfolders = [ 'world', 'languages' ]
        )

    ########################################################################

    @property
    def characters( self ):

        return utilities.generic_table_getter(
            self,
            'characters',
            self.world_dir,
            subfolders = [ 'world', 'characters' ]
        )

    ########################################################################

    @property
    def nodes( self ):

        return utilities.generic_table_getter(
            self,
            'nodes',
            self.world_dir,
            subfolders = [ 'world', 'settings' ]
        )

    ########################################################################
    # Methods
    ########################################################################

    def sample_part( self, part_name, n_samples=1 ):

        part = getattr( self, part_name )

        ind = prob_tools.sample_discrete_probabilities(
            part['Likelihood'].values,
            normalize = True
        )

        if n_samples == 1:
            return part.loc[ind]
        else:
            raise Exception( "Multiple samples not implemented yet." )
