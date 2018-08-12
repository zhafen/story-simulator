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

import story_simulator.read_data.language as read_language_data

import hoard.utils.utilities as utilities
import hoard.utils.probability_tools as prob_tools

########################################################################
########################################################################

class Name( read_language_data.LanguageDataReader ):

    @utilities.store_parameters
    def __init__(
        self,
        n_p_min = 2,
        n_p_max = 4,
        vowel_chain = [ 0.25, 0.05 ],
        consonant_chain = [ 0.5, 0.02 ],
        language = None,
        generated_language = None,
        **kwargs
    ):
        '''Constructor.

        Args:
            n_p_min, n_p_max (int) :
                Minimum/maximum number of phonemes in the name.

            vowel_chain, consonant_chain (array-like) :
                The ith index is the probability that there will be a chain of
                i+2 vowels/consonants, given that there is already a chain of
                i+1 vowels/consonants.
                If the ith index doesn't exist, the probability is zero.
                TODO: I'd really like to make it that s.t. these aren't
                conditional_probabililities, but are the percentages of the
                time that we have particular words.

            language (pd.Series):
                If given, create words from this language.

            generated_language (object) :
                If given, create words from this language.

        Kwargs:
            phonemes (str or array-like) :
                List of phonemes to use.

            phonemes_dir (str) :
                The directory the phonemes data is stored in. Defaults to the
                directory this file is stored in.
        '''

        # Load parameters from the language, if it's given
        language_attrs = [
            'n_p_min',
            'n_p_max',
            'vowel_chain',
            'consonant_chain',
        ]
        if language is not None:
            def read_chain( chain ):
                l = chain[1:-1].split(', ')
                return [ float( item ) for item in l ]
            self.vowel_chain = read_chain( language['Vowel Chain'] )
            self.consonant_chain = read_chain( language['Consonant Chain'] )
            phonemes = language['Phonemes'][1:-1]
            phonemes = phonemes.replace( "'\n '", "' '" )
            phonemes = phonemes.split( "' '" )
            phonemes[0] = phonemes[0][1:]
            phonemes[-1] = phonemes[-1][:-1]
            kwargs['phonemes'] = phonemes
            kwargs['phonemes_dir'] = language['Phonemes Dir']

        if generated_language is not None:
            for attr in language_attrs:
                setattr( self, attr, getattr( generated_language, attr ) )
            kwargs['phonemes'] = generated_language.phonemes
            kwargs['phonemes_dir'] = generated_language.phonemes_dir

        super( Name, self ).__init__( **kwargs )

        # Actually generate the name
        self.generate_name()

    def __repr__( self ):
        return self.name

    ########################################################################
    # Properties
    ########################################################################

    @property
    def name( self ):
        '''Name using the default spelling'''

        return self.name_data['Default Spelling'].values.sum().capitalize()

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



