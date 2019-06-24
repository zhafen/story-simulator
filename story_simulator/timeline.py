#!/usr/bin/env python
'''Timeline object, for reading and editing the timelines of individual
characters/places/objects.
'''

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
    ):
        pass

    ########################################################################

    def save( self ):

        pass
