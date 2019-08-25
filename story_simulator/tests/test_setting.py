#!/usr/bin/env python
'''Testing for Timeline objects.
'''

import copy
import h5py
import numpy as np
import numpy.testing as npt
import os
import unittest
import unyt

import story_simulator.world as world
import story_simulator.setting as setting

########################################################################

def assert_dict_equal( a, b ):
    for key, item in a.items():
        if isinstance( item, dict ):
            assert_dict_equal( a[key], b[key] )
        else:
            if isinstance( a[key], str ):
                assert a[key] == b[key]
            elif isinstance( a[key], unyt.unyt_quantity ):
                npt.assert_allclose( a[key], b[key] )
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

    # def test_from_generated_character( self ):
    #     '''This also acts as a test for the character generator.'''

    #     g_char = character_generator.GeneratedCharacter(
    #         self.w,
    #         request_user_input = False,
    #     )
    #     g_char.generate_character()

    #     c = character.Character.from_generated_character( g_char, 0.1 )

    #     # Try opening data that should be stored
    #     actual = c.get_state( 1. )
    #     print( actual['name'] )
    #     print( actual['mental_state']['personality_traits'] )
    #     print( actual['mental_state']['quirks'] )
    #     print( actual['physical_state']['eye_color'] )
    #     print( actual['physical_state']['hair_color'] )
    #     print( actual['physical_state']['skin_tone'] )
    #     print( actual['physical_state']['height'] )
    #     print( actual['physical_state']['gender'] )
    #     print( actual['mental_state']['gender_identity'] )
    #     print( actual['mental_state']['sexual_orientation'] )
    #     print( c.t_update, 0.1 )

    ########################################################################

    def test_basic( self ):
        '''This also creates the basic test rooms.
        '''
        data = {
            'name': {
                'x': np.array([ 'Testing Complex', ]),
                't': np.array([ 0. ]),
            },
            'description': {
                'x': np.array([ 'A building containing rooms for testing', ]),
                't': np.array([ 0. ]),
            },
            'dimensions': {
                'x': np.array([ [ 15., 10., 5., ] ]),
                't': np.array([ 0. ]),
            },
        }
        self.set = setting.Setting(
            self.w,
            'Testing Complex',
            data = data,
        )
        self.set.save()

        for l in [ 'A', 'B', 'C' ]:

            name = 'Test Room {}'.format( l )

            resides_in = [ 'Testing Complex', ]

            data = {
                'name': {
                    'x': np.array([ name, ]),
                    't': np.array([ 0. ]),
                },
                'description': {
                    'x': np.array([ 'An empty white room.', ]),
                    't': np.array([ 0. ]),
                },
                'dimensions': {
                    'x': np.array([ [ 5., 5., 5., ] ]),
                    't': np.array([ 0. ]),
                },
            }
            self.set = setting.Setting(
                self.w,
                name,
                data = data,
                resides_in = resides_in,
            )

            expected_data_dir = (
                './tests/world_test_data/world/settings/Testing_Complex/Test_Room_{}'.format(
                    l
                )
            )
            assert self.set.data_dir == expected_data_dir
            assert self.set.filename == 'Test_Room_{}.tld'.format( l )

            state = self.set.get_state( 1. )
            assert state['name'] == name
            assert state['description'] == 'An empty white room.'
            npt.assert_allclose(
                np.array([ 5., 5., 5. ]),
                state['dimensions'].astype( float )
            )

            self.set.save()
            self.set.load(
                self.w,
                name,
                resides_in = resides_in,
            )

########################################################################

class TestSetting( unittest.TestCase ):

    def setUp( self ):

        self.w = world.World( './tests/world_test_data' )

        # Load our standard test character
        self.set = setting.Setting.load( self.w, 'Testing Complex' )
    
    ########################################################################

    def test_contained_settings( self ):

        expected = [ 'Test Room A', 'Test Room B', 'Test Room C', ]
        assert self.set.contained_settings == expected
