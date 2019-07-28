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

import story_simulator.character as character
import story_simulator.language as language
import story_simulator.config as ss_config
import story_simulator.utils.utils as utils
import story_simulator.generator.name as gen_name
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
        request_user_input = True,
    ):
        '''Constructor.

        Args:
            world (object):
                The world this is being constructed for.

            data_dir (str):
                Where the data used to generate characters is stored.
                Defaults to the story_simulator overall data dir
        '''

        self.data = {}
        self.data['mental_state'] = {}
        self.data['physical_state'] = {}

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

    def generate_name( self, language_name=None, **kwargs ):

        if language_name is not None:
            l = language.Language( language_name, self.world, )
        else:
            l = None

        self.name = gen_name.Name( language=l, **kwargs )

        print( 'Name = {}'.format( self.name ) )

        self.data['name'] = self.name.__repr__()

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

    def combine_and_store_traits( self, ):
        '''Store the traits in the data dict.'''

        self.data['mental_state']['personality_traits'] = {}
        for trait in self.pos_traits['Description'].values:
            self.data['mental_state']['personality_traits'][trait] = 1
        for trait in self.neg_traits['Description'].values:
            self.data['mental_state']['personality_traits'][trait] = 1

    ########################################################################

    def generate_quirks( self, ):
        '''Generate n quirks.'''

        self.quirks = prob_tools.sample_table(
            self.quirks_table,
            self.n_quirks,
        )

        # Store quirks in a timeline-like format
        self.data['mental_state']['quirks'] = {}
        for quirk in self.quirks['Description'].values:
            self.data['mental_state']['quirks'][quirk] = 1

        return self.quirks

    ########################################################################

    def generate_eye_color( self, ):

        eye_color = gen_utils.generate_color( self.request_user_input )

        self.data['physical_state']['eye_color'] = eye_color 

    ########################################################################

    def generate_hair_color( self, ):

        hair_color = gen_utils.generate_color( self.request_user_input )

        self.data['physical_state']['hair_color'] = hair_color 

    ########################################################################

    def generate_skin_tone( self, ):

        skin_tone = gen_utils.generate_color( self.request_user_input )

        self.data['physical_state']['skin_tone'] = skin_tone 

    ########################################################################

    def generate_height( self, avg_height=175., sigma_height=50. ):

        height = np.random.normal( avg_height, sigma_height )

        self.data['physical_state']['height'] = height 

        print( 'height = {:.3g} cm ({:.3g} feet)'.format(
                height,
                height*0.0328084,
            )
        )

    ########################################################################

    def generate_character( self ):
        '''Actual generating function for generating a character.
        Usually it's preferable not to use this, and instead create a character
        interactively in a notebook.
        '''

        # Name, ofc
        self.generate_name()

        # Generate mental state
        self.generate_positive_traits()
        self.generate_negative_traits()
        self.combine_and_store_traits()
        self.generate_quirks()

        # Generate physical state
        self.generate_eye_color()
        self.generate_hair_color()
        self.generate_skin_tone()
        self.generate_height()

    ########################################################################

    def save( self, t ):

        char = character.Character.from_generated_character( self, t )

        return char
