#!/usr/bin/env python
'''Testing for Timeline objects.
'''

import copy
import h5py
import numpy as np
import numpy.testing as npt
import os
import unittest

import story_simulator.character as character
import story_simulator.world as world
import story_simulator.generator.character as character_generator

########################################################################

def assert_dict_equal( a, b ):
    for key, item in a.items():
        if isinstance( item, dict ):
            assert_dict_equal( a[key], b[key] )
        else:
            if isinstance( a[key], str ):
                assert a[key] == b[key]
            elif hasattr( a[key], '__len__' ):
                for i, a_val in enumerate( a[key] ):
                    if isinstance( a_val, str ):
                        assert a_val == b[key][i]
                    elif np.isnan( a_val ) and np.isnan( b[key][i] ):
                        continue
                    else:
                        assert a_val == b[key][i]
            elif np.isnan( a[key] ):
                assert np.isnan( b[key] )
            else:
                npt.assert_allclose( a[key], b[key] )

########################################################################
########################################################################

class TestConstructors( unittest.TestCase ):

    def setUp( self ):

        self.w = world.World( './tests/world_test_data' )

    ########################################################################

    def test_from_generated_character( self ):
        '''This also acts as a test for the character generator.'''

        g_char = character_generator.GeneratedCharacter(
            self.w,
            request_user_input = False,
        )
        g_char.generate_character()

        c = character.Character.from_generated_character( g_char, 0.1 )

        # Try opening data that should be stored
        actual = c.get_state( 1. )
        print( actual['name'] )
        print( actual['mental_state']['personality_traits'] )
        print( actual['mental_state']['quirks'] )
        print( actual['physical_state']['eye_color'] )
        print( actual['physical_state']['hair_color'] )
        print( actual['physical_state']['skin_tone'] )
        print( actual['physical_state']['height'] )
        print( actual['physical_state']['gender'] )
        print( actual['mental_state']['gender_identity'] )
        print( actual['mental_state']['sexual_orientation'] )

        assert False, "Need to make sure the statistics of gender and sexual orientation look right."

########################################################################

class TestCharacter( unittest.TestCase ):

    def setUp( self ):

        self.w = world.World( './tests/world_test_data' )

        c = character.Character.load( self.w, 'Ohh' )
    
    ########################################################################

    def test_begin_action( self ):

        #DEBUG
        import pdb; pdb.set_trace()

        assert False
