#!/usr/bin/env python
'''Testing for world

@author: Zach Hafen
@contact: zachary.h.hafen@gmail.com
@status: Development
'''

import numpy as np
import numpy.testing as npt
import os
import unittest

import story_simulator.world as world

########################################################################
########################################################################

class TestWorld( unittest.TestCase ):

    def setUp( self ):

        self.w = world.World( './tests/world_test_data' )

    ########################################################################

    def test_constructor( self ):
        '''If the constructor works then this will just pass.'''

        pass

        
        
