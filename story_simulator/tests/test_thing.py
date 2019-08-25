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
import story_simulator.thing as thing

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
            'description': {
                'x': np.array([ 'A simple table with four legs, made of some sort of white wood.', ]),
                't': np.array([ 0. ]),
            },
            'dimensions': {
                'x': np.array([ [ 1., 0.75, 0.75 ] ]),
                't': np.array([ 0. ]),
            },
            'position': {
                'description': {
                    'x': np.array([ 'Middle of the room.', ]),
                    't': np.array([ 0. ]),
                },
            }
        }
        self.table = thing.Thing(
            self.w,
            'a white table',
            data = data,
            resides_in = [ 'Testing Complex', 'Test Room A', ],
        )
        assert self.table.data_dir == os.path.join(
            self.w.world_dir,
            'world',
            'Testing_Complex',
            'Test_Room_A',
            'things',
            'a_white_table',
        )

        self.table.save()
        self.table = thing.Thing.load(
            self.w,
            'a white table',
            resides_in = [ 'Testing Complex', 'Test Room A', ],
        )

        data = {
            'description': {
                'x': np.array([ 'A simple chair, made of some sort of white wood.', ]),
                't': np.array([ 0. ]),
            },
            'dimensions': {
                'x': np.array([ [ 1., 0.75, 0.75 ] ]),
                't': np.array([ 0. ]),
            },
            'position': {
                'description': {
                    'x': np.array([ 'Middle of the room, tucked into the table.', ]),
                    't': np.array([ 0. ]),
                },
            }
        }
        self.chair = thing.Thing(
            self.w,
            'Testing Complex/Test Room A/a white chair',
            data = data,
        )
        assert self.chair.data_dir == os.path.join(
            self.w.world_dir,
            'world',
            'Testing_Complex',
            'Test_Room_A',
            'things',
            'a_white_chair',
        )
        self.chair.save()
        self.chair = thing.Thing.load(
            self.w,
            'Testing Complex/Test Room A/a white chair',
        )

########################################################################

class TestSetting( unittest.TestCase ):

    def setUp( self ):

        self.w = world.World( './tests/world_test_data' )

        # Load our standard test character
        self.set = setting.Setting.load( self.w, 'Testing Complex' )
    
    ########################################################################
