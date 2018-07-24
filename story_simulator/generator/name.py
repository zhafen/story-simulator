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
        vowel_likelihoods = [ 0.25, 0.05 ],
        consonant_likelihoods = [ 0.5, 0.02 ],
        phonemes_dir = None,
        phonemes = 'all',
    ):
        '''Constructor.

        Args:
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

        if self.phonemes == 'all':
            return self.phonemes_table

        raise Exception( "Not implemented yet." )

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

        # TODO: Implement this
        pass

    ########################################################################
    # Methods
    ########################################################################

    def generate_name( self ):
        # TODO: Allow there to be a flow of consonants and vowels
        # This is probably easiest to implement as probability of there being
        # subsequent consonants or vowels

        # Get the number of letters in the word
        if self.n_p_min != self.n_p_max:
            self.n_p = np.random.randint( self.n_p_min, self.n_p_max )
        else:
            self.n_p = self.n_p_max

        # Get the individual phenomes
        self.name_data = []
        for i in range( self.n_p ):

            if i == 0:
                phoneme_name = np.random.choice( self.available_phonemes.index )
            elif i == 1:
                if self.name_data[0]['Vowel']:
                    if np.random.uniform() < self.vowel_likelihoods:
                        phoneme_name = np.random.choice( self.available_vowels.index )
                    else:
                        phoneme_name = np.random.choice( self.available_consonants.index )
                else:
                    if np.random.uniform() < self.consonant_likelihoods:
                        phoneme_name = np.random.choice( self.available_consonants.index )
                    else:
                        phoneme_name = np.random.choice( self.available_vowels.index )

            phoneme = self.available_phonemes.loc[phoneme_name]

            self.name_data.append( phoneme )
        
        # Put it all together
        self.name_data = pd.concat( self.name_data, axis=1 ).transpose()



