#!/usr/bin/env python
'''Objects and function for creating and dealing with characters.

@author: Zach Hafen
@contact: zachary.h.hafen@gmail.com
@status: Development
'''

import collections
import hickle as hkl
import numpy as np
import os
import pandas as pd
import pickle
import verdict

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
        ongoing_action_start_time = 'Not set',
        **kwargs
    ):

        super( Character, self ).__init__(
            data_dir = world.get_element_dir( name, 'characters' ),
            filename = world.get_element_timeline_filename( name ),
            **kwargs
        )
    
        self.name = name

        # Set up some initial action states
        self.action_queue = collections.deque()
        self.ongoing_action = None
        self.ongoing_action_start_time = ongoing_action_start_time

    def __repr__( self ):

        return 'Char {}; Ongoing action: {}'.format(
            self.name,
            self.ongoing_action
        )

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

        # Load the raw data
        result = verdict.Dict.from_hdf5(
            os.path.join( data_dir, filename ),
            unpack = True,
            unpack_name = 'unpack_name'
        )
        if isinstance( result, tuple ):
            v_d, params = result
        else:
            v_d = result
            params = {}

        # Create the main class
        c = Character(
            world = world,
            name = name,
            data = v_d._storage,
            **params
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
        try:
            next_action = self.action_queue.popleft()
        # When there are no new planned actions
        except IndexError:
            next_action = self.determine_course_of_action()

        # Update the expected time to finish at
        self.t_update = t + next_action.time_to_complete

        # Record the action as part of the log
        self.store_state( { 'actions': [ str( next_action ) ] }, t )

        # Add the action to the list of ongoing actions
        self.ongoing_action = next_action
        self.ongoing_action_start_time = t

    ########################################################################
    # Properties
    ########################################################################

    @property
    def params( self ):
        '''Important parameters for the character, all in one spot.'''

        # Start with the parameters of the parent class
        params = super( Character, self ).params
        
        # Include other important parameters
        params['ongoing_action_start_time'] = self.ongoing_action_start_time

        return params
        

