#!/usr/bin/env python
'''Testing for settings.py

@author: Zach Hafen
@contact: zachary.h.hafen@gmail.com
@status: Development
'''

import numpy as np
import numpy.testing as npt
import os
import unittest

import story_simulator.generator.name as name_generator

########################################################################
########################################################################

class TestName( unittest.TestCase ):

    def test_available_consonants_and_vowels( self ):

        name = name_generator.Name()

        # Make sure there are no consonants or vowels mixed up
        assert name.available_consonants['Vowel'].sum() == 0
        assert name.available_vowels['Vowel'].sum() == len( name.available_vowels )

        # Make sure we have all the letters
        assert len( name.available_vowels ) + len( name.available_consonants ) == len( name.available_phonemes )

    ########################################################################

    def test_generate_name_consonants_and_vowels( self ):

        # Set up a random seed for reproducibility.
        # Numbers produced are 0.19, 0.62, 0.437
        # np.random.seed( 1234 )

        vowel_likelihoods = [ 0.25, 0.15, 0.1 ]
        consonant_likelihoods = [ 0.2, 0.1, 0.05 ]

        n_samples = 1000
        n_letters = 3
        n_vowels = np.zeros( n_letters )
        for i in range( n_samples ):

            name = name_generator.Name(
                n_p_min = n_letters,
                n_p_max = n_letters,
                vowel_likelihoods = vowel_likelihoods,
                consonant_likelihoods = consonant_likelihoods,
            )

            n_vowels += name.name_data['Vowel'].values.astype( int )

        # Calculate the expected probabilities
        n_available_vowels = name.available_phonemes['Vowel'].sum()
        n_available_phonemes = len( name.available_phonemes )
        p_first_vowel = float( n_available_vowels ) / n_available_phonemes
        p_second_vowel = p_first_vowel * vowel_likelihoods[0] + \
                ( 1. - p_first_vowel ) * ( 1. - consonant_likelihoods[0] )
        p_second_consonant = p_first_vowel * ( 1. - vowel_likelihoods[0] ) + \
                ( 1. - p_first_vowel ) * consonant_likelihoods[0]
        p_third_vowel = p_first_vowel * vowel_likelihoods[1] + \
                ( 1. - p_first_vowel ) * consonant_likelihoods[1] + \
                p_second_vowel * vowel_likelihoods[0] + \
                p_second_consonant * ( 1. - consonant_likelihoods[0] )

        actual = n_vowels.astype( float ) / n_samples
        expected = np.array([
            p_first_vowel,
            p_second_vowel,
            p_third_vowel,
        ])
        npt.assert_allclose( expected, actual )
                

