#!/usr/bin/env python
'''Testing for Timeline objects.
'''

import h5py
import numpy as np
import numpy.testing as npt
import os
import unittest

import story_simulator.timeline as tline

########################################################################
########################################################################

class TestTimeline( unittest.TestCase ):

    def setUp( self ):

        world_dir = './tests/world_test_data/generic_tline_data'
        filename = 'test.tld'
        self.d = {
            'A': {
                'x': np.array([ 1, 5, 3 ]),
                't': np.array([ 0., 2., 5. ]),
            },
            'outer': {
                'B': {
                    'x': [ 'red', 'blue' ],
                    't': np.array([ 0., 4. ]),
                },
                'C': {
                    'x': [ 'large and long', 'small and straight' ],
                    't': np.array([ 2., 4. ]),
                },
            },
        }

        self.tl = tline.Timeline(
            world_dir,
            filename,
            self.d,
        )

        # Remove any existing files
        self.test_file = os.path.join( world_dir, filename )
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

    def test_get_state( self ):

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
