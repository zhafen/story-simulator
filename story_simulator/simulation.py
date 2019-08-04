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

    def identify_scene_to_advance( self ):
        '''Determine which scene to advance.

        Returns:
            int:
                The index for the scene that will be advanced.
        '''

        scene_id = np.argmin( self.scenes['t_update'] )

        return scene_id

    ########################################################################

    def start_advancing_scene( self, scene_id ):

        # Load the scene
        self.load_scene( scene_id )
