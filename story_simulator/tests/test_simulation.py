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

import story_simulator.simulation as ss
import story_simulator.world as world
import story_simulator.actions.common as common_acts

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

class TestSimulation( unittest.TestCase ):

    def setUp( self ):

        self.world_dir = './tests/world_test_data/'
        self.w = world.World( self.world_dir )
        self.s = ss.Simulation(
            self.w,
        )
        self.s.scenes = {
            'characters': np.array([
                [ 'Rue', ],
                [ 'Pau', 'Dau', 'Jshoh', ],
                [ 'uRue', ],
            ]),
            'settings': np.array([
                'Test Room A',
                'Test Room B',
                'Test Room C',
            ]),
            't_update': np.array([ 5., 1., 25. ]),
        }

    ########################################################################

    def test_constructor( self ):
        '''If the setUp goes okay, this passes.'''

        pass

    ########################################################################

    def test_load_scene( self ):

        self.s.load_scene( 1 )

        # Check of at least one of the characters loaded properly
        j = self.s.loaded_scene['characters']['Jshoh']
        j_state = j.get_state( 1. )
        assert j_state['position']['description'] == 'SE corner of the room.'
        assert j.ongoing_action.__repr__() == 'actions.common.Walk'

        # Test that the room loaded properly
        r = self.s.loaded_scene['setting']
        r_state = r.get_state( 1. )
        assert r_state['name'] == 'Test Room B'

    ########################################################################

    def test_identify_scene_to_advance( self ):

        # Test case
        self.s.scenes = {
            't_update': np.array([ 3.5, 0.1, 3600., 3., ]),
        }
        scene_id = self.s.identify_scene_to_advance()
        assert scene_id == 1

    ########################################################################

    def test_advance_scene( self ):

        # Setup
        scene_id = 1

        # Advance a scene
        actor_state, other_states = self.s.start_advancing_scene( scene_id )
        assert actor_state['position']['description'] == 'Middle of the room.'
        self.s.finish_advancing_scene( scene_id, actor_state, other_states )

        # Check that a variety of results are as expected
        expected = np.array([ 5., 3.67142, 25. ])
        npt.assert_allclose( expected, self.s.scenes['t_update'] )
        e_pau_state = self.s.loaded_scene['Pau'].get_state( 1. )
        assert e_pau_state['position']['description'] == 'NW corner of the room.'
        assert e_pau_state['mental_state']['gender_identity'] == 'female'
        assert e_pau_state['actions'] == 'actions.common.Walk'
        npt.assert_allclose(
            self.s.loaded_scene['Pau'].t_update,
            0.1 + 5./1.4,
        )
        npt.assert_allclose(
            self.s.loaded_scene['Dau'].t_update,
            0.1 + 5./1.4,
        )
        npt.assert_allclose(
            self.s.loaded_scene['Jshoh'].t_update,
            0.1 + 10.*np.sqrt( 2. )/1.4,
        )
        
