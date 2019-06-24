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
        d = {
            'A': {
                'x': np.array([ 1, 5, 3 ]),
                't': np.array([ 0., 2., 5. ]),
            },
            'B': {
                'x': [ 'red', 'blue' ],
                't': np.array([ 0., 4. ]),
            },
            'C': {
                'x': [ 'large and long', 'small and straight' ],
                't': np.array([ 2., 4. ]),
            },
        }

        self.tl = tline.Timeline(
            world_dir,
            filename,
            d,
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

        f = h5py.File( self.test_file, 'r' )
