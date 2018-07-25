#!/usr/bin/env python
'''Functions for generating names.

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

import story_simulator.generator.name as name_generator

########################################################################
########################################################################

class GeneratedLanguage( object ):

    @utilities.store_parameters
    def __init__(
        self,
        name = None,
        n_p_min = [ 1, 2 ],
        n_p_max = [ 1, 7 ],
        vowel_chain = None,
        consonant_chain = None,
        phonemes = None,
        n_available_vowels = [ 2, 20 ],
        n_available_consonants = [ 2, 20 ],
        phonemes_dir = None,
    ):
        '''Constructor.

        Args:
            world (object) :
                The world this is being constructed for.

            n_p_min, n_p_max (int) :
                Minimum/maximum number of phonemes in the name.

            vowel_chain, consonant_chain (array-like) :
                The ith index is the probability that there will be a chain of i+2 vowels/consonants,
                given that there is already a chain of i+1 vowels/consonants.
                If the ith index doesn't exist, the probability is zero.

            phonemes (str or array-like) :
                List of phonemes to use.

            phonemes_dir (str) :
                The directory the phonemes data is stored in. Defaults to the
                directory this file is stored in.

        Phonemes:
            What phonemes in particular to use?
        '''

        if phonemes_dir is None:
            self.phonemes_dir = os.path.dirname( os.path.realpath( __file__ ) )

        # Actually generate the name
        self.generate_language()

    ########################################################################
    # Properties
    ########################################################################

    @property
    def phonemes_table( self ):
        '''Data used to create words.'''

        return utilities.generic_table_getter(
            self,
            property_name = 'phonemes_table',
            root_folder = self.phonemes_dir,
            index_col = 0,
        )

    ########################################################################
    # Methods
    ########################################################################

    def generate_language( self ):
        '''Actual generating function.'''

        # Generate minimum and maximum number of phonemes
        if not isinstance( self.n_p_min, int ):
            self.n_p_min = np.random.randint(
                self.n_p_min[0],
                self.n_p_min[1],
            )
        if not isinstance( self.n_p_max, int ):
            self.n_p_max = np.random.randint(
                self.n_p_max[0],
                self.n_p_max[1],
            )

        if self.name is None:
            self.name = name_generator.Name(
                n_p_min = self.n_p_min,
                n_p_max = self.n_p_max,
                vowel_chain = self.vowel_chain,
                consonant_chain = self.consonant_chain,
                phonemes = self.phonemes,
                phonemes_dir = self.phonemes_dir,
            )


