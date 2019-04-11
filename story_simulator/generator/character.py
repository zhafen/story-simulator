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
import story_simulator.utils.utils as utils
import story_simulator.generator.utils as gen_utils

########################################################################
########################################################################

class GeneratedCharacter( object ):

    @utilities.store_parameters
    def __init__(
        self,
        world,
        data_dir = ss_config.DATA_DIR,
        n_pos_traits = 2,
        n_neg_traits = 2,
        n_quirks = 2,
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

    def generate_positive_traits( self, ):
        '''Generate positive traits.'''

        self.pos_traits = prob_tools.sample_table(
            self.pos_traits_table,
            self.n_pos_traits,
        )

        return self.pos_traits

    def generate_negative_traits( self, ):
        '''Generate n negative traits.'''

        self.neg_traits = prob_tools.sample_table(
            self.neg_traits_table,
            self.n_neg_traits,
        )

        return self.neg_traits

    ########################################################################

    def generate_quirks( self, ):
        '''Generate n quirks.'''

        self.quirks = prob_tools.sample_table(
            self.quirks_table,
            self.n_quirks,
        )

        return self.quirks

    ########################################################################

    def generate_eye_color( self, ):

        self.eye_color = gen_utils.generate_color()

    ########################################################################

    def generate_hair_color( self, ):

        self.hair_color = gen_utils.generate_color()

    ########################################################################

    def generate_skin_tone( self, ):

        self.skin_tone = gen_utils.generate_color()

    ########################################################################

    def generate_height( self, avg_height=175., sigma_height=50. ):

        self.height = np.random.normal( avg_height, sigma_height )

        print( 'height = {:.3g} cm ({:.3g} feet)'.format(
                self.height,
                self.height*0.0328084,
            )
        )

    ########################################################################

    def generate_character( self ):
        '''Actual generating function for generating a character.'''

        # Generate traits
        self.generate_positive_traits()
        self.generate_negative_traits()

        # Generate quirks
        self.generate_quirks()

