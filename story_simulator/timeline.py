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

                # Allow some room for error
                t_sufficient = t + self.time_error >= item['t']
                if t_sufficient.sum() == 0:
                    return np.nan

                ind = np.argmax( t_sufficient )
                return item['x'][ind]

            else:
                result = {}
                for i_key, i_item in item.items():
                     result[i_key] = get_state_or_go_deeper( i_item )

                return result

        return get_state_or_go_deeper( self.data )
