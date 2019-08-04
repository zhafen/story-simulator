#!/usr/bin/env python
'''Timeline object, for reading and editing the timelines of individual
characters/places/objects.
'''

import copy
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
        data_dir,
        filename,
        data,
        time_error = 0.1,
        t_update = 'Not set',
    ):

        pass

    ########################################################################

    @classmethod
    def load(
        cls,
        data_dir,
        filename,
    ):
        '''Create a Timeline object by loading from a file.

        Args:
            data_dir (str):
                Directory containing the timeline data.

            filename (str):
                Filename of the file containing the timeline data.
                Timeline files usually end in *.tld .

        Returns:
            Timeline: A timeline instance.
        '''

        # Set up the filepath
        filepath = os.path.join(
            data_dir,
            filename,
        )

        result = verdict.Dict.from_hdf5(
            filepath,
            unpack = True,
            unpack_name = 'unpack_name'
        )

        if isinstance( result, tuple ):
            v_d, params = result
        else:
            v_d = result
            params = {}

        return Timeline(
            data_dir,
            filename,
            v_d._storage,
            **params
        )

    ########################################################################

    def save( self, attrs={} ):
        '''Save the raw Timeline data.

        Args:
            attrs (dict):
                Attributes to save (beyond particular parameters that will
                be stored for sure, like t_update).
        '''

        # Set up the filepath
        filepath = os.path.join(
            self.data_dir,
            self.filename,
        )

        # Set up attributes
        full_attrs = self.params.copy()
        full_attrs.update( attrs )

        # Save
        v_d = verdict.Dict( self.data )
        v_d.to_hdf5( filepath, attributes=full_attrs )
        
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

    def store_state( self, state, t ):
        '''Save the state (or a substate) of the system at time t.
        This will update the timeline data accordingly.

        Args:
            state (dict):
                Dictionary containing values you want to record at time t.

            t (float):
                Time at which you want to update the state of the timeline.
        '''

        def store_state_or_go_deeper( state_item, data_item ):
            '''Recursive function for saving the state.'''

            if not isinstance( state_item, dict ):

                new_item = copy.deepcopy( data_item )


                inds = self.get_ind(
                    t,
                    data_item['t'],
                )

                # We want to place after, not before
                inds += 1

                # Increase the size of string arrays when necessary.
                x_dtype_str = data_item['x'].dtype.str
                if x_dtype_str[:-1] == '<U':
                    current_arr_lim = int( x_dtype_str[2:] )
                    state_item_dtype_str = np.array( state_item ).dtype.str
                    len_s_item = int( state_item_dtype_str[2:] )
                    if len_s_item > current_arr_lim:
                        data_item['x'] = data_item['x'].astype(
                            '<U{}'.format( len_s_item )
                        )

                # Make the new items.
                new_item['t'] = np.insert( data_item['t'], inds, t )
                try:
                    new_item['x'] = np.insert(
                        data_item['x'],
                        inds,
                        state_item,
                        axis = 0
                    )

                # Sometimes we need to expand the array
                except ValueError:
                    # TODO: Optimization opportunity (too much copying)
                    new_shape = ( data_item['x'].shape[0], len( state_item ) )
                    new_item['x'] = np.full(
                        new_shape,
                        fill_value = np.nan,
                    ).astype( data_item['x'].dtype )
                    new_item['x'][:,:data_item['x'].shape[1]] = data_item['x']
                    new_item['x'] = np.insert(
                        new_item['x'],
                        inds,
                        state_item,
                        axis = 0
                    )

                return new_item

            else:

                # Combine the data keys to cover everything
                state_keys = set( state_item.keys() )
                data_keys = set( data_item.keys() )
                all_keys = state_keys.union( data_keys )

                result = {}
                for i_key in all_keys:

                    in_state = i_key in state_keys
                    in_data = i_key in data_keys

                    # Account for all ways of mixing and matching keys
                    if in_state and in_data:
                        result[i_key] = store_state_or_go_deeper(
                            state_item[i_key],
                            data_item[i_key],
                        )

                    if in_data and not in_state:
                        result[i_key] = data_item[i_key]

                    if in_state and not in_data:

                        def format_state( item ):
                            '''Recursive function to format state'''
                            if isinstance( item, dict ):
                                result = {}
                                for ii_key, ii_item in item.items():
                                    result[ii_key] = format_state( ii_item )
                            else:
                                result = {
                                    'x': np.array([ item ]),
                                    't': np.array([ t ]),
                                }
                            return result

                        result[i_key] = format_state( state_item[i_key] )

                return result

        self.data = store_state_or_go_deeper( state, self.data )

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
        if len( item_x.shape ) > 1:
            # This is in case we have stored an array in the timeline
            x_shape = ( t_in_arr.size, item_x.shape[1] )
        else:
            x_shape = t_in_arr.shape
        x_result = np.full( x_shape, np.nan, dtype=object )
        valid_inds = ind_result != fill_value
        x_result[valid_inds] = np.array( item_x )[ind_result[valid_inds]]

        return ind_result, x_result
        
    ########################################################################
    # Properties (focusing on parameters)
    ########################################################################

    @property
    def params( self ):
        '''Important parameters for the timeline, all in one spot.'''

        return {
            't_update': self.t_update,
            'time_error': self.time_error,
        }
        
