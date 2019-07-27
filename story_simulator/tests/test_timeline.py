#!/usr/bin/env python
'''Testing for Timeline objects.
'''

import copy
import h5py
import numpy as np
import numpy.testing as npt
import os
import unittest

import story_simulator.timeline as tline

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
                    elif isinstance( a_val, np.ndarray ):
                        try:
                            npt.assert_allclose( a[key], b[key] )
                        except TypeError:
                            for i in range( a[key].shape[0] ):
                                for j in range( a[key].shape[1] ):
                                    assert a[key][i,j] == b[key][i,j]
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

class TestTimeline( unittest.TestCase ):

    def setUp( self ):

        self.data_dir = './tests/world_test_data/generic_tline_data'
        self.filename = 'test.tld'
        self.d = {
            'A': {
                'x': np.array([ 1, 5, 3 ]),
                't': np.array([ 0., 2., 5. ]),
            },
            'outer': {
                'B': {
                    'x': np.array([ 'red', 'blue' ]),
                    't': np.array([ 0., 4. ]),
                },
                'C': {
                    'x': np.array(
                        [ 'large and long', 'small and straight' ],
                    ),
                    't': np.array([ 2., 4. ]),
                },
            },
        }

        self.tl = tline.Timeline(
            self.data_dir,
            self.filename,
            self.d,
        )

        # Remove any existing files
        self.test_file = os.path.join( self.data_dir, self.filename )
        if os.path.isfile( self.test_file ):
            os.remove( self.test_file )

    ########################################################################

    def test_constructor( self ):
        '''If the setUp goes okay, this passes.'''

        pass

    ########################################################################

    def test_saves( self ):

        self.tl.save()

        # Check contents
        f = h5py.File( self.test_file, 'r' )
        npt.assert_allclose( self.d['A']['x'], f['A']['x'][...] )
        assert self.d['outer']['B']['x'][0] == f['outer']['B']['x'][...][0]

    ########################################################################

    def test_loads( self ):

        tl = tline.Timeline.load(
            self.data_dir,
            'test_loads.tld'
        )

        npt.assert_allclose( tl.params['time_error'], 0.001 )

    ########################################################################

    def test_get_state( self ):

        # Test for single t values
        expected = {
            'A': 1,
            'outer': {
                'B': 'red',
                'C': np.nan,
            },
        }
        actual = self.tl.get_state( 0. )
        assert_dict_equal( expected, actual )

        # Test for t arrays
        expected = {
            'A': np.array([ np.nan, 1, 5, 5, 3, ], dtype=object),
            'outer': {
                'B': np.array(
                    [ np.nan, 'red', 'red', 'blue', 'blue' ],
                    dtype=object
                ),
                'C': np.array([
                    np.nan, np.nan, 'large and long', 'small and straight',
                    'small and straight'
                ], dtype=object),
            },
        }
        actual = self.tl.get_state(
            np.array([ -0.5, -0.05, 3., 4.5, np.inf ])
        )
        assert_dict_equal( expected, actual )

    ########################################################################

    def test_store_state( self ):
        '''Test save a state or substate.
        '''

        expected = copy.deepcopy( self.tl.data )
        expected['A'] = {
            'x': np.array([ 1, 2, 5, 3 ]),
            't': np.array([ 0., 0.5, 2., 5. ]),
        }
        expected['outer']['B'] = {
            'x': np.array([ 'red', 'green', 'blue' ]),
            't': np.array([ 0., 0.5, 4. ]),
        }
        expected['new'] = {
            'D': {
                'x': np.array([ 'x' ]),
                't': np.array([ 0.5 ]),
            }
        }
        expected['unknown'] = {
            'x': np.array([ 1e17 ]),
            't': np.array([ 0.5 ]),
        }

        # Single addition
        self.tl.store_state(
            t = 0.5,
            state = {
                'A': 2,
                'outer': {
                    'B': 'green',
                },
                'new': {
                    'D': 'x',
                },
                'unknown': 1e17,
            }
        )
        assert_dict_equal( expected, self.tl.data )

    ########################################################################

    def test_store_and_get_state_array( self ):
        '''Test we can store a state that' an array.
        '''

        # Simple inclusion
        expected = copy.deepcopy( self.tl.data )
        expected['A_arr'] = {
            'x': np.array([ [ 1., 1., ], ]),
            't': np.array([ 15., ]),
        }
        self.tl.store_state(
            t = 15.,
            state = { 'A_arr': np.array([ 1., 1., ]) },
        )
        assert_dict_equal( expected, self.tl.data )

        # More complicated case
        expected['outer_arr'] = {}
        expected['outer_arr']['B_arr'] = {
            'x': np.array([
                [ 'red', 'also_red', 'nan', ],
                [ 'green', 'also_green', 'yeah_its_green', ],
                [ 'blue', 'also_blue', 'nan' ],
            ]),
            't': np.array([  16., 17., 18., ]),
        }
        self.tl.store_state(
            t = 16.,
            state = { 'outer_arr': {
                'B_arr': [ 'red', 'also_red', ],
            }}
        )
        self.tl.store_state(
            t = 18.,
            state = { 'outer_arr': {
                'B_arr': [ 'blue', 'also_blue', ],
            }}
        )
        self.tl.store_state(
            t = 17.,
            state = { 'outer_arr': {
                'B_arr': [ 'green', 'also_green', 'yeah_its_green', ],
            }}
        )
        assert_dict_equal( expected, self.tl.data )

        # Get state
        actual = self.tl.get_state( 16.5 )
        expected_A_arr = np.array([1., 1.,])
        npt.assert_allclose( expected_A_arr, actual['A_arr'].astype( float ) )
        expected_B_arr = np.array([ 'red', 'also_red', 'nan' ])
        for i, val in enumerate( expected_B_arr ):
            assert val == actual['outer_arr']['B_arr'][i]
        assert 3 == actual['A']

        # Get state for multiple t values
        actual = self.tl.get_state( np.array([ 16.5, 17.5, ]) )
        expected_A_arr = np.array([1., 1.,])
        actual_A_arr = actual['A_arr'][0].astype( float )
        npt.assert_allclose( expected_A_arr, actual_A_arr )
        actual_A_arr = actual['A_arr'][1].astype( float )
        npt.assert_allclose( expected_A_arr, actual_A_arr )
        expected_B_arr = np.array([ 'red', 'also_red', 'nan' ])
        for i, val in enumerate( expected_B_arr ):
            assert val == actual['outer_arr']['B_arr'][0][i]
        expected_B_arr = np.array([ 'green', 'also_green', 'yeah_its_green', ])
        for i, val in enumerate( expected_B_arr ):
            assert val == actual['outer_arr']['B_arr'][1][i]
        assert 3 == actual['A'][0]
        assert 3 == actual['A'][1]
