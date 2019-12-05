#!/usr/bin/env python
'''Actions centered around deciding the next action to take.

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

class SurveyOptions( object ):
    '''Survey the actions available to take.

    Args:
        surveying_timescale (float):
            Average time it takes to survey available options.
    '''

    @utilities.store_parameters
    def __init__(
        self,
        surveying_timescale = 0.3,
    ):

        pass

    def __repr__( self ):

        return 'actions.intelligence.manual.DetermineCourseOfAction'

    ########################################################################

    @property
    def time_to_complete( self ):
        '''Determine how long the action will take to complete. This is a
        standard property for actions.

        Returns:
            float:
                The time to complete this action in seconds.
        '''

        return self.surveying_timescale

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

        assert False, "Need to do."

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

        assert False, "Need to do."

########################################################################

class DetermineActions( object ):
    '''
    Args:
        complexity (float):
            Exponential factor that determines how long the decision will take.
        decision_making_timescale (float):
            Normalization for the decision making timescale, in seconds.
    '''

    @utilities.store_parameters
    def __init__(
        self,
        complexity,
        decision_making_timescale = 0.3,
    ):

        pass

    def __repr__( self ):

        return 'actions.intelligence.manual.DetermineCourseOfAction'

    ########################################################################

    @property
    def time_to_complete( self ):
        '''Determine how long the action will take to complete. This is a
        standard property for actions.

        Returns:
            float:
                The time to complete this action in seconds.
        '''

        return self.decision_making_timescale * np.exp( self.complexity )

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

        assert False, "Need to do."

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

        assert False, "Need to do."
