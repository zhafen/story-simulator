#!/usr/bin/env python
'''Objects and function for creating and dealing with characters.

@author: Zach Hafen
@contact: zachary.h.hafen@gmail.com
@status: Development
'''

import hickle as hkl
import numpy as np
import os
import pandas as pd
import pickle
import collections

import hoard.utils.utilities as utilities

from . import timeline

########################################################################
########################################################################

class Character( timeline.Timeline ):

    # Attributes to implement
    # action_queue
    # current_actions
    # processing_power
    # t_update
    # parameters that decide abilities to do actions

    def __init__(
        self,
        world,
        name,
        **kwargs
    ):

        super( Character, self ).__init__(
            data_dir = world.get_element_dir( name, 'characters' ),
            filename = world.get_element_timeline_filename( name ),
            **kwargs
        )

        self.action_queue = collections.deque()
        self.ongoing_action = None

    ########################################################################
    # Constructors
    ########################################################################

    @classmethod
    def from_generated_character( cls, gen_char, t ):
        '''Retrieve from a generated character.'''

        c = Character(
            world = gen_char.world,
            name = gen_char.data['name'],
            data = {},
            t_update = t,
        )
        c.store_state( gen_char.data, t )

        return c

    ########################################################################

    @classmethod
    def load( cls, world, name ):
        '''Load a character from an existing file.

        Args:
            world (World object):
                The object representing the world this character exists in.

            name (str):
                Name of the character.
        '''

        data_dir = world.get_element_dir( name, 'characters' )
        filename = world.get_element_timeline_filename( name )
        
        tl = super( Character, cls ).load( data_dir, filename )
        c = Character(
            world = world,
            name = name,
            data = tl.data,
            **tl.params
        )

        # Load the action queue
        action_queue_filepath = os.path.join(
            data_dir,
            'action_queue.hkl'
        )
        if os.path.isfile( action_queue_filepath ):
            c.action_queue = collections.deque(
                hkl.load( action_queue_filepath )
            )

        # Load the ongoing action
        ongoing_action_filepath = os.path.join(
            data_dir,
            'ongoing_action.hkl'
        )
        if os.path.isfile( ongoing_action_filepath ):
            c.ongoing_action = hkl.load( ongoing_action_filepath )

        return c

    ########################################################################

    def save( self ):

        # Save the action queue
        action_queue_filepath = os.path.join(
            self.data_dir,
            'action_queue.hkl'
        )
        l = list( self.action_queue )
        hkl.dump( l, action_queue_filepath, 'w' )

        # Save the ongoing action
        ongoing_action_filepath = os.path.join(
            self.data_dir,
            'ongoing_action.hkl'
        )
        hkl.dump( self.ongoing_action, ongoing_action_filepath, 'w' )

        super( Character, self ).save()

    ########################################################################
    # Related to actions
    ########################################################################

    def get_result_of_ongoing_action( self, t ):
        '''Get the results of the ongoing action, if it was to stop at
        time t.

        Args:
            t (float):
                Time (universal time in seconds) to get action results.
        '''

        elapsed_time = t - self.ongoing_action_start_time

        return self.ongoing_action.result_of_action( elapsed_time )

    ########################################################################

    def begin_action( self, t ):
        '''Begin the next action in the queue.

        Args:
            t (float):
                Time (universal time in seconds) at which to begin the action.
        '''

        # Get the next action
        next_action = self.action_queue.popleft()

        # Update the expected time to finish at
        self.t_update += next_action.time_to_complete

        # Add the action to the list of ongoing actions
        self.ongoing_action = next_action
        self.ongoing_action_start_time = t
