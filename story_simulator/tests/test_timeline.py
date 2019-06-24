#!/usr/bin/env python
'''Testing for Timeline objects.
'''

import numpy as np
import numpy.testing as npt
import os
import unittest

import story_simulator.timeline as tline

########################################################################
########################################################################

class TestTimeline( unittest.TestCase ):

    def setUp( self ):

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
            './tests/world_test_data/generic_tline_data',
            data = d,
        )

    ########################################################################

    def test_constructor( self ):
        '''If the setUp goes okay, this passes.'''

        pass
