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

import story_simulator.generator.language as language_generator

########################################################################
########################################################################

class TestGeneratedLanguage( unittest.TestCase ):

    def test_generated_language_all_args_passed( self ):
        '''Make sure we can make it work in its most basic form.'''

        language = language_generator.GeneratedLanguage(
            n_p_min = 2,
            n_p_max = 5,
            vowel_chain = [ 0.05, ],
            consonant_chain = [ 0.4, 0.05 ],
        )

        actual = language.name.name_data['Default Spelling'].values.sum() 
        assert isinstance( actual, basestring )

    ########################################################################

    def test_works_no_n_ps( self ):

        language = language_generator.GeneratedLanguage(
            vowel_chain = [ 0.05, ],
            consonant_chain = [ 0.4, 0.05 ],
        )

    ########################################################################

    def test_works_no_chains( self ):

        language = language_generator.GeneratedLanguage(
            n_p_min = 2,
            n_p_max = 5,
        )
