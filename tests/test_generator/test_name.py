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
        np.random.seed( 1234 )

        n_letters = 3
        vowel_c = [ 0.25, 0.15, 0.1 ]
        consonant_c = [ 0.2, 0.1, 0.05 ]

        # Initial name draw to allow us to calc the probabilities
        name = name_generator.Name(
            n_p_min = n_letters,
            n_p_max = n_letters,
            vowel_chain = vowel_c,
            consonant_chain = consonant_c,
        )

        # Calculate the expected probabilities
        n_available_vowels = name.available_phonemes['Vowel'].sum()
        n_available_phonemes = len( name.available_phonemes )
        p_first_vowel = float( n_available_vowels ) / n_available_phonemes

        # Probabilities for the second letter being a vowel
        p_second_vowel = p_first_vowel * vowel_c[0] + \
                ( 1. - p_first_vowel ) * ( 1. - consonant_c[0] )
        p_second_consonant = p_first_vowel * ( 1. - vowel_c[0] ) + \
                ( 1. - p_first_vowel ) * consonant_c[0]
        npt.assert_allclose( p_second_vowel + p_second_consonant, 1. )

        # Probabilities for the third letter being a vowel
        # The ways we can get to the third phoneme as a vowel are:
        # VVV
        # VCV
        # CCV
        # CVV
        p_third_vowel = (
            p_first_vowel * vowel_c[0] * vowel_c[1] +
            p_first_vowel * ( 1. - vowel_c[0] ) * ( 1. - consonant_c[0] ) +
            ( 1. - p_first_vowel ) * consonant_c[0] * ( 1. - consonant_c[1] ) +
            ( 1. - p_first_vowel ) * ( 1. - consonant_c[0] ) * vowel_c[0]
        )
        # To make sure our math is right, let's calculate the probability of getting
        # the third phoneme as a consonant. Combinations are...
        # CCC
        # CVC
        # VVC
        # VCC
        p_third_consonant = (
            (1. - p_first_vowel ) * consonant_c[0] * consonant_c[1] +
            (1. - p_first_vowel ) * ( 1. - consonant_c[0] ) * ( 1. - vowel_c[0] ) +
            p_first_vowel * vowel_c[0] * ( 1. - vowel_c[1] ) +
            p_first_vowel * ( 1. - vowel_c[0] ) * consonant_c[0]
        )
        # Our check
        npt.assert_allclose( p_third_vowel + p_third_consonant, 1. )

        # Sample the name generator
        n_samples = 1000
        n_vowels = np.zeros( n_letters )
        for i in range( n_samples ):

            name = name_generator.Name(
                n_p_min = n_letters,
                n_p_max = n_letters,
                vowel_chain = vowel_c,
                consonant_chain = consonant_c,
            )

            n_vowels += name.name_data['Vowel'].values.astype( int )


        actual = n_vowels.astype( float ) / n_samples
        expected = np.array([
            p_first_vowel,
            p_second_vowel,
            p_third_vowel,
        ])
        npt.assert_allclose( expected, actual, atol=0.02 )
                
