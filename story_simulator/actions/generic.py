#!/usr/bin/env python
'''Generic actions available to characters

@author: Zach Hafen
@contact: zachary.h.hafen@gmail.com
@status: Development
'''

import numpy as np
import os
import pandas as pd
import unyt

import hoard.utils.utilities as utilities

########################################################################
########################################################################

class Walk( object ):

    @utilities.store_parameters
    def __init__(
        self,
        new_position,
        displacement,
        speed = 1.4,
    ):

        # Attach MKS units if not given
        if not isinstance( self.displacement, unyt.unyt_quantity ):
            self.displacement *= unyt.m
        if not isinstance( self.speed, unyt.unyt_quantity ):
            self.speed *= unyt.m / unyt.s

    ########################################################################

    @property
    def time_to_complete( self ):
        '''Determine how long the action will take to complete. This is a
        standard property for actions.

        Returns:
            float:
                The time to complete this action in seconds.
        '''

        if not hasattr( self, '_time_to_complete' ):

            t = self.displacement / self.speed
            self._time_to_complete = t.to( 's' ).value

        return self._time_to_complete

    ########################################################################

    def result_of_action( self, elapsed_time ):
        '''Result of the action given a time elapsed

        Args:
            elapsed_time (float):
                Time (in seconds) since the action started.

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

        if elapsed_time < self.time_to_complete:
            return self.upon_interruption( elapsed_time )
        else:
            return self.upon_completion()

    ########################################################################

    def upon_completion( self ):
        '''Result of action upon completion.

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

        actor_state = {
            'position': {
                'description': self.new_position,
            },
        }

        other_states = {}

        aux_info = {}

        return actor_state, other_states, aux_info

    ########################################################################

    def upon_interruption( self, elapsed_time ):
        '''Result of action upon interruption.

        Args:
            elapsed_time (float):
                Time (in seconds) since the action started.

        Returns:
            tuple: tuple containing:
                actor_state (dict):
                    Updated state of actor upon interruption of action.
                other_states (dict):
                    Updated states of other elements upon interruption.
                    A dictionary of states, with the key as the element name.
                aux_info (dict):
                    Dictionary of miscellanious additional info.
        '''

        actor_state = {
            'position': {
                'description': 'CREATE',
            },
        }

        other_states = {}

        aux_info = {
            'meters_walked': ( self.speed * elapsed_time * unyt.s ).to( 'm' )
        }

        return actor_state, other_states, aux_info
