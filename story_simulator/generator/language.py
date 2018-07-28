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
import story_simulator.read_data.language as read_language_data

########################################################################
########################################################################

class GeneratedLanguage( read_language_data.LanguageDataReader ):

    @utilities.store_parameters
    def __init__(
        self,
        name = None,
        n_p_min = [ 1, 2 ],
        n_p_max = [ 1, 7 ],
        vowel_chain = None,
        consonant_chain = None,
        choose_phonemes = True,
        n_available_vowels = [ 2, 10 ],
        n_available_consonants = [ 2, 10 ],
        **kwargs
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

        Kwargs:
            phonemes (str or array-like) :
                List of phonemes to use.

            phonemes_dir (str) :
                The directory the phonemes data is stored in. Defaults to the
                directory this file is stored in.
        '''

        super( GeneratedLanguage, self ).__init__( **kwargs )

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

        # Generate chain probabilities
        if self.vowel_chain is None:
            chain_length = np.random.randint( 0, 3 )
            self.vowel_chain = [
                np.random.uniform() * ( i + 1. )**-2. \
                for i in range( chain_length)
            ]
        if self.consonant_chain is None:
            chain_length = np.random.randint( 0, 3 )
            self.consonant_chain = [
                np.random.uniform() * ( 1. + chain_length - i )**-2. \
                for i in range( chain_length)
            ]

        # Generate phonemes
        if self.phonemes is not None and self.choose_phonemes:
            raise Exception(
                "Cannot both generate phonemes and take in a list of phonemes"
            )
        if self.choose_phonemes:
            self.phonemes = self.generate_phonemes()
        else:
            self.phonemes = phonemes

        # Generate a name if not given
        if self.name is None:
            self.name = name_generator.Name(
                n_p_min = self.n_p_min,
                n_p_max = self.n_p_max,
                vowel_chain = self.vowel_chain,
                consonant_chain = self.consonant_chain,
                phonemes = self.phonemes,
                phonemes_dir = self.phonemes_dir,
            )

    ########################################################################

    def generate_phonemes( self ):
        '''Choose what phonemes are used in the language.'''

        # Generate phonemes
        def choose_n_available( vowels_or_consonants, table ):
            '''Helper function for choosing the number available.'''

            if isinstance( self.n_available_vowels, list ):
                n_available = np.random.randint(
                    self.n_available_vowels[0],
                    self.n_available_vowels[1] + 1,
                )
            else:
                n_available = vowels_or_consonants

            # We can't choose more than are available
            n_table = len( table )
            if n_available > n_table:
                n_available = n_table
            return n_available

        n_available_vowels = choose_n_available(
            self.n_available_vowels,
            self.vowels,
        )
        n_available_consonants = choose_n_available(
            self.n_available_consonants,
            self.consonants,
        )

        # Get the actual phonemes
        vowels = np.random.choice(
            self.vowels.index,
            size = n_available_vowels,
            replace = False,
        )
        consonants = np.random.choice(
            self.consonants.index,
            size = n_available_consonants,
            replace = False,
        )
        phonemes = np.concatenate( [ vowels, consonants ] )

        return phonemes
