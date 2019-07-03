#!/usr/bin/env python
'''Timeline object, for reading and editing the timelines of individual
characters/places/objects.
'''

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

        def get_state_or_go_deeper( item ):
            '''Recursive function for getting the state.'''

            if list( item.keys() ) == [ 'x', 't' ]:

                inds, x_vals = self.get_ind_and_val(
                    t,
                    item['t'],
                    item['x'],
                )

                return x_vals

            else:
                result = {}
                for i_key, i_item in item.items():
                     result[i_key] = get_state_or_go_deeper( i_item )

                return result

        return get_state_or_go_deeper( self.data )

    ########################################################################

    def get_ind_and_val( self, t, item_t, item_x ):

        # Treat t as a list, one way or another.
        if hasattr(t, "__len__"):
            t_in_arr = t
        else:
            t_in_arr = np.array( [ t, ] )

        def numba_get_ind_and_val( t_in_arr, t_arr, x_arr, time_error ):
            '''Function for finding the appropriate time in the timeline.'''

            ind_result = np.full( t_in_arr.shape, np.nan )
            x_result = np.full( t_in_arr.shape, np.nan, dtype=type( x_arr ) )

            # if t_in_arr.size > 1:
            #     #DEBUG
            #     import pdb; pdb.set_trace()

            # Loop through t_ins
            for i, t_in in enumerate( t_in_arr ):

                # Loop through t_arrs to find maximum time that fits
                ind = len( t_arr ) - 1
                while t_in + time_error < t_arr[ind]:

                    # if t_in_arr.size > 1:
                    #     #DEBUG
                    #     import pdb; pdb.set_trace()
                                
                    ind -= 1

                    # Stop when we go past the end of the array
                    if ind == -1:
                        break

                if ind == -1:
                    continue

                ind_result[i] = ind
                x_result[i] = x_arr[ind]

            if len( x_result ) == 1:
                return ind_result[0], x_result[0]

            return ind_result, x_result

        return numba_get_ind_and_val(
            t_in_arr,
            item_t,
            item_x,
            self.time_error
        )
            
