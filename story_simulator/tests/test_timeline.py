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

        expected = {
            'A': 1,
            'outer': {
                'B': 'red',
                'C': np.nan,
            },
        }
        actual = self.tl.get_state( 0. )

        assert expected == actual
