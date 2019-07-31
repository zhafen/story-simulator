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
import scipy.stats

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

        return height

    ########################################################################

    def generate_gender( self, m_to_w_ratio=1.06 ):
        '''Generate the gender of the character.
        TODO: Update this to include intersex.

        Args:
            m_to_w_ratio (float):
                Ratio of men to women in the population this
                character comes from.

        Returns:
            str:
                A string indicating the gender, typically male or female.
        '''

        ps = np.array( [ m_to_w_ratio, 1. ] )
        ind = prob_tools.sample_discrete_probabilities( ps )
        
        self.gender = [ 'male', 'female' ][ind]

        self.data['physical_state']['gender'] = self.gender

        return self.gender

    ########################################################################

    def generate_gender_identity( self, frac_transgender=0.02 ):
        '''Generate the gender identity of the character.
        TODO: Update this to include agender, bigender, and generally a more
        fluid definition.

        Args:
            frac_transgender (float):
                The fraction of transgender individuals in the population this
                character comes from.

        Returns:
            str:
                A string indicating the gender identity,
                typically male or female.
        '''

        ps = np.array( [ 1. - frac_transgender, frac_transgender ] )
        ind = prob_tools.sample_discrete_probabilities( ps )

        # Dictionary for mapping gender allignment
        ordered_genders = {
            'female': [ 'female', 'male', ],
            'male': [ 'male', 'female', ],
        }
        ordered_gender_list = ordered_genders[self.gender]
        self.gender_identity = ordered_gender_list[ind]

        self.data['mental_state']['gender_identity'] = self.gender_identity

        # We also store the ordered gender list for use in determining
        # sexual orientation
        self.ordered_gender_list = ordered_genders[self.gender_identity]

        return self.gender_identity

    ########################################################################

    def generate_sexual_orientation(
        self,
        mean_frac_attr_same = 0.1,
        scale_same = 2.,
        mean_frac_attr_opp = 'from_frac_same',
        scale_opp = 2.,
    ):
        '''
        '''

        # We find the center of the distribution by noting that a value of 0
        # is the breakpoint between being more attracted than not to a gender
        # (with positive being more attracted), so we can correspond that
        # to the number of sigma the location should be away from 0
        frac_not_attr = 1. - mean_frac_attr_same 
        n_sigma_loc_same = -1. * scipy.stats.norm.ppf( frac_not_attr )
        loc_same = n_sigma_loc_same * scale_same
 
        # Similar for opposite gender
        if mean_frac_attr_opp == 'from_frac_same':
            frac_not_attr = mean_frac_attr_same
        else:
            frac_not_attr = 1. - mean_frac_attr_opp
        n_sigma_loc_opp = -1. * scipy.stats.norm.ppf( frac_not_attr )
        loc_opp = n_sigma_loc_opp * scale_opp

        # Now draw from those distributions
        ori_same = np.random.normal( loc=loc_same, scale=scale_same )
        ori_opp = np.random.normal( loc=loc_opp, scale=scale_opp )

        # Scale these (which range from -inf to +inf) to 0 to 1
        def map_to_0_to_1( x ):
            return 1. / ( 1. + np.exp( -x ) )
        ori_same = map_to_0_to_1( ori_same )
        ori_opp = map_to_0_to_1( ori_opp )

        # Actual dictionary
        self.sexual_orientation = {}
        # Same sex attraction
        self.sexual_orientation[self.ordered_gender_list[0]] = ori_same
        # Opposite sex attraction
        self.sexual_orientation[self.ordered_gender_list[1]] = ori_opp

        self.data['mental_state']['sexual_orientation'] = (
            self.sexual_orientation
        )

        return self.sexual_orientation

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

        # Gender, gender identity, and sexual orientation
        self.generate_gender()
        self.generate_gender_identity()
        self.generate_sexual_orientation()

    ########################################################################

    def save( self, t ):

        char = character.Character.from_generated_character( self, t )

        return char
