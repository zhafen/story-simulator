#!/usr/bin/env python
'''Testing for Generic Actions
'''

import copy
import h5py
import numpy as np
import numpy.testing as npt
import os
import unittest
import unyt

import story_simulator.actions.generic as generic_actions

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

class TestWalk( unittest.TestCase ):

    def setUp( self ):

        self.action = generic_actions.Walk(
            new_position = 'right side of the room',
            displacement = 4.,
            speed = 1.5,
        )

    ########################################################################

    def test_time_to_complete( self ):

        actual = self.action.time_to_complete

        expected = ( 4. / 1.5 )

        npt.assert_allclose( expected, actual )

    ########################################################################

    def test_upon_completion( self ):

        actual = self.action.upon_completion()

        expected_actor_state = {
            'position': {
                'description': 'right side of the room'
            }
        }
        assert_dict_equal( expected_actor_state, actual[0] )

        expected_other_states = {}
        assert_dict_equal( expected_other_states, actual[1] )

        expected_aux_info = {}
        assert_dict_equal( expected_aux_info, actual[2] )

    ########################################################################

    def test_upon_interruption( self ):

        elapsed_time = 2.
        
        actual = self.action.upon_interruption( elapsed_time )

        expected_actor_state = {
            'position': {
                'description': 'CREATE'
            }
        }
        assert_dict_equal( expected_actor_state, actual[0] )

        expected_other_states = {}
        assert_dict_equal( expected_other_states, actual[1] )

        expected_aux_info = {
            'meters_walked': 1.5 * elapsed_time * unyt.m
        }
        assert_dict_equal( expected_aux_info, actual[2] )
