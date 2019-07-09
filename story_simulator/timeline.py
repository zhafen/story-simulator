#!/usr/bin/env python
'''Timeline object, for reading and editing the timelines of individual
characters/places/objects.
'''

import numba
import numpy as np
import os

import verdict
import hoard.utils.utilities as utilities

########################################################################
########################################################################

class Timeline( object ):
    '''A complete Timeline object should include:
    - Loading timeline data
    - Saving updated timelines
    - Retrieving the state of an object at given times
    - Saving a timeline narrative(s)
    - Tagging other timelines
    '''

    @utilities.store_parameters
    def __init__(
        self,
        world_dir,
        filename,
        data,
        time_error = 0.1,
    ):
        pass

    ########################################################################

    def save( self ):
        '''Save the raw Timeline data.
        '''

        # Set up the filepath
        filepath = os.path.join(
            self.world_dir,
            self.filename,
        )

        # Save
        v_d = verdict.Dict( self.data )
        v_d.to_hdf5( filepath )
        
    ########################################################################

    def get_state( self, t ):
        '''Get the state of the timeline at time(s) t.

        Args:
            t (float or np.ndarray):
                Time(s) at which you want to get the state of the timeline.

        Returns:
            dict : State of the timeline at time(s) t, i.e. a dictionary
            containing the most up-to-date values of the timeline prior to t.
        '''

        def get_state_or_go_deeper( item ):
            '''Recursive function for getting the state.'''

            if list( item.keys() ) == [ 'x', 't' ]:

                inds, x_vals = self.get_ind(
                    t,
                    item['t'],
                    item['x'],
                )

                if len( x_vals ) == 1:
                    return x_vals[0]

                return x_vals

            else:
                result = {}
                for i_key, i_item in item.items():
                     result[i_key] = get_state_or_go_deeper( i_item )

                return result

        return get_state_or_go_deeper( self.data )

    ########################################################################

    def get_ind( self, t, item_t, item_x=None ):
        '''For a time or series of times, get the corresponding indices
        of the stored times that are the most recent prior times in item_t.
        Can also retrieve the corresponding value at the most recent prior
        times.

        Args:
            t (float or np.ndarray):
                Times at which you want to find the corresponding indices
                (and optionally values).

            item_t (np.ndarray):
                Times at which data exists.

            item_x (np.ndarray, optional):
                Values of the data at the times given by item_t.

        Returns:
            np.ndarray or tuple of ndarrays: The indices of the times
            closest to, but still before, the values given by t. If
            item_x is passed this is a tuple, and the second array gives the
            values of x at those times.
        '''

        # Treat t as a list, one way or another.
        if hasattr(t, "__len__"):
            t_in_arr = t
        else:
            t_in_arr = np.array( [ t, ] )

        def conditional_njit( condition, *args, **kwargs ):
            '''Only turn njit on under particular conditions, e.g. if the array
            is large enough.
            '''
            
            def wrapper( function ):
                if condition:
                    return numba.njit( *args, **kwargs )(function)
                else:
                    return function

            return wrapper

        @conditional_njit(
            len( t_in_arr ) > 100,
            'int64[:](int64[:], float64[:], float64[:], float64)',
        )
        def numba_get_ind(
            ind_result,
            t_in_arr,
            t_arr,
            time_error,
        ):
            '''Function for finding the appropriate time in the timeline.'''

            # Loop through t_ins
            for i, t_in in enumerate( t_in_arr ):

                # Loop through t_arrs to find maximum time that fits
                ind = len( t_arr ) - 1
                while t_in + time_error < t_arr[ind]:

                    ind -= 1

                    # Stop when we go past the end of the array
                    if ind == -1:
                        break

                if ind == -1:
                    continue

                ind_result[i] = ind

            return ind_result

        fill_value = -9999999999
        ind_result = np.full( t_in_arr.shape, fill_value )
        ind_result = numba_get_ind(
            ind_result,
            t_in_arr,
            item_t,
            self.time_error
        )

        # Simple case
        if item_x is None:
            return ind_result

        # Case where we want to return x's as well
        x_result = np.full( t_in_arr.shape, np.nan, dtype=object )
        valid_inds = ind_result != fill_value
        x_result[valid_inds] = np.array( item_x )[ind_result[valid_inds]]

        return ind_result, x_result
        
