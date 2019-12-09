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
        '''Load all the elements of a scene into memory.

        Args:
            scene_id (int): Index for the scene to load.
        '''

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
        '''Starts moving a scene forward, stopping at the point where
        manual feedback might be applied.

        Args:
            scene_id (int):
                Index for the scene to advance.

        Returns:
            tuple: tuple containing:
                actor_state (dict):
                    Updated state of actor upon completion of action.
                other_states (dict):
                    Updated states of other elements upon completion.
                    A dictionary of states, with the key as the element name.
                aux_info (dict):
                    Dictionary of miscellanious additional info.
        '''

        # Load the scene
        self.load_scene( scene_id )

        # Identify the character to advance
        char_name, self.t = self.loaded_scene['characters'].t_update.keymin()

        # Load the actor
        self.actor = self.loaded_scene['characters'][char_name]

        return self.actor.get_result_of_ongoing_action( self.t )

    ########################################################################

    def finish_advancing_scene( self, scene_id, actor_state, other_states ):
        '''Finishes advancing a scene_forward, potentially after taking in
        manual input.


        Args:
            scene_id (int):
                Index for the scene to advance.

            actor_state (dict):
                Updated state of actor upon completion of action.

            other_states (dict):
                Updated states of other elements upon completion.
                A dictionary of states, with the key as the element name.
        '''

        # Load the scene
        self.load_scene( scene_id )

        # Finish advancing the actor
        self.actor.finish_action( actor_state, self.t )
        self.actor.begin_action( self.t )

        # Store the other states
        for other_name, other_state in other_states.items():
            other_element = self.loaded_scene['characters'][other_name]
            other_element.store_state( other_state, self.t )

        # Update t_update
        self.scenes['t_update'][scene_id] = (
            self.loaded_scene['characters'].t_update.keymin()[1]
        )
