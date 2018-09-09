#!/usr/bin/env python
'''Code for generating characters.

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

import story_simulator.config as ss_config

########################################################################
########################################################################

class GeneratedCharacter( object ):

    @utilities.store_parameters
    def __init__(
        self,
        world,
        data_dir = ss_config.DATA_DIR,
    ):
        '''Constructor.

        Args:
            world (object):
                The world this is being constructed for.

            data_dir (str):
                Where the data used to generate characters is stored.
                Defaults to the story_simulator overall data dir
        '''

        # Generate the character.
        self.generate_character()

    ########################################################################
    # Properties
    ########################################################################

    @property
    def traits_table( self ):
        '''Database of character traits.'''

        return utilities.generic_table_getter(
            self,
            property_name = 'character_traits',
            root_folder = self.data_dir,
        )

    @property
    def pos_traits_table( self ):

        return self.traits_table[self.traits_table['Positivity'] > 0.]

    @property
    def neg_traits_table( self ):

        return self.traits_table[self.traits_table['Positivity'] < 0.]

    ########################################################################

    @property
    def quirks_table( self ):
        '''Database of character quirks.'''

        return utilities.generic_table_getter(
            self,
            property_name = 'character_quirks',
            root_folder = self.data_dir,
        )

    ########################################################################
    # Methods
    ########################################################################

    def generate_positive_traits( self, n ):
        '''Generate n positive traits.'''

        self.pos_traits = prob_tools.sample_table(
            self.pos_traits_table,
            n,
        )

        return self.pos_traits

    def generate_negative_traits( self, n ):
        '''Generate n negative traits.'''

        self.neg_traits = prob_tools.sample_table(
            self.neg_traits_table,
            n,
        )

        return self.neg_traits

    ########################################################################

    def generate_quirks( self, n ):
        '''Generate n quirks.'''

    ########################################################################

    def generate_character( self ):
        '''Actual generating function for generating a character.'''

        pass
