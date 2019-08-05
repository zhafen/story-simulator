#!/usr/bin/env python
'''Main story simulation.

@author: Zach Hafen
@contact: zachary.h.hafen@gmail.com
@status: Development
'''

import numpy as np
import verdict

import hoard.utils.utilities as utilities
from . import setting
from . import character

########################################################################
########################################################################

class Simulation( object ):

    @utilities.store_parameters
    def __init__(
        self,
        world,
    ):
        pass

        self.loaded_scene_id = None

    ########################################################################

    def load_scene( self, scene_id ):

        # Don't reload if already loaded
        if self.loaded_scene_id == scene_id:
            return

        # Create base structure
        self.loaded_scene = {}

        # Load Setting
        self.loaded_scene['setting'] = setting.Setting.load(
            self.world,
            self.scenes['settings'][scene_id],
        )

        # Load Characters
        cs = {}
        for c_name in self.scenes['characters'][scene_id]:
            cs[c_name] = character.Character.load(
                self.world,
                c_name,
            )
        self.loaded_scene['characters'] = cs

        # Turn into a verdict Dict for easier manipulation
        self.loaded_scene = verdict.Dict( self.loaded_scene )

        self.loaded_scene_id = scene_id

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
