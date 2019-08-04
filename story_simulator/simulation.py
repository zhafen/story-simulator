#!/usr/bin/env python
'''Main story simulation.

@author: Zach Hafen
@contact: zachary.h.hafen@gmail.com
@status: Development
'''

import numpy as np

import hoard.utils.utilities as utilities

########################################################################
########################################################################

class Simulation( object ):

    @utilities.store_parameters
    def __init__(
        self,
        world_dir,
    ):
        pass

    ########################################################################

    def identify_seq_to_advance( self ):

        seq_id = np.argmin( self.sequences['t_update'] )

        return seq_id

    ########################################################################

    def advance_sequence( self, seq_id ):

        pass
