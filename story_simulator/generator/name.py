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

########################################################################
########################################################################

class Name( object ):

    @utilities.store_parameters
    def __init__(
        self,
        n_p_min = 2,
        n_p_max = 4,
        vowel_chain = [ 0.25, 0.05 ],
        consonant_chain = [ 0.5, 0.02 ],
        phonemes = None,
        phonemes_dir = None,
    ):
        '''Constructor.

        Args:
            n_p_min, n_p_max (int) :
                Minimum/maximum number of phonemes in the name.

            vowel_chain, consonant_chain (array-like) :
                The ith index is the probability that there will be a chain of i+2 vowels/consonants,
                given that there is already a chain of i+1 vowels/consonants.
                If the ith index doesn't exist, the probability is zero.
                TODO: I'd really like to make it that s.t. these aren't conditional_probabililities,
                but are the percentages of the time that we have particular words.

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
        self.generate_name()

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

    @property
    def available_phonemes( self ):
        '''Actual data used'''

        if self.phonemes is None:
            return self.phonemes_table

        # Case where particular phonemes are selected
        else:
            if not hasattr( self, '_available_phonemes' ):
                self._available_phonemes = self.phonemes_table.loc[self.phonemes]
            return self._available_phonemes

    ########################################################################

    @property
    def available_vowels( self ):
        return self.available_phonemes.loc[self.available_phonemes['Vowel']]

    @property
    def available_consonants( self ):
        return self.available_phonemes.loc[np.invert(self.available_phonemes['Vowel'])]

    ########################################################################

    @property
    def name( self ):
        '''Name using the default spelling'''

        return self.name_data['Default Spelling'].values.sum()

    ########################################################################
    # Methods
    ########################################################################

    def generate_name( self ):

        # Get the number of letters in the word
        if self.n_p_min != self.n_p_max:
            self.n_p = np.random.randint( self.n_p_min, self.n_p_max )
        else:
            self.n_p = self.n_p_max

        def get_phoneme( phonemes_df ):
            '''Helper function for getting a phoneme.'''
            phoneme_name = np.random.choice( phonemes_df.index )
            return self.available_phonemes.loc[phoneme_name]

        # Get the individual phenomes
        self.name_data = []
        for i in range( self.n_p ):

            if i == 0:
                phoneme = get_phoneme( self.available_phonemes )

                # Start up a chain
                j0 = 0
                chain_vowel = phoneme['Vowel']

            else:
                j = i - 1 - j0

                # Vowel chain case
                if chain_vowel:

                    # Account for chains ending early
                    try:
                        p_vowel = self.vowel_chain[j]
                    except IndexError:
                        p_vowel = 0.

                    # Vowel chain continues case
                    if np.random.uniform() < p_vowel:
                        phoneme = get_phoneme( self.available_vowels )

                    # Vowel chain ends case
                    else:
                        phoneme = get_phoneme( self.available_consonants )

                        # Start a new chain
                        j0 = i
                        chain_vowel = phoneme['Vowel']

                # Consonant chain case
                else:

                    # Account for chains ending early
                    try:
                        p_consonant = self.consonant_chain[j]
                    except IndexError:
                        p_consonant = 0.

                    # Consonant chain continues case
                    if np.random.uniform() < p_consonant:
                        phoneme = get_phoneme( self.available_consonants )

                    # Consonant chain ends case
                    else:
                        phoneme = get_phoneme( self.available_vowels )

                        # Start a new chain
                        j0 = i
                        chain_vowel = phoneme['Vowel']

            # Store the phoneme
            self.name_data.append( phoneme )
        
        # Put it all together
        self.name_data = pd.concat( self.name_data, axis=1 ).transpose()



