#!/usr/bin/env python
'''Objects and function for creating and dealing with things (i.e. objects)

@author: Zach Hafen
@contact: zachary.h.hafen@gmail.com
@status: Development
'''

import numpy as np
import os
import pandas as pd
import queue

import hoard.utils.utilities as utilities

from . import timeline

########################################################################
########################################################################

class Thing( timeline.Timeline ):

    def __init__(
        self,
        world,
        name,
        resides_in = [],
        **kwargs
    ):

        super( Thing, self ).__init__(
            data_dir = world.get_element_dir(
                name,
                'things',
                subdirs = resides_in,
                element_type_ind = -1,
            ),
            filename = world.get_element_timeline_filename( name ),
            **kwargs
        )

        self.action_queue = queue.Queue()

    ########################################################################
    # Constructors
    ########################################################################

    @classmethod
    def load( cls, world, name, resides_in=[] ):
        '''Load a thing from an existing file.

        Args:
            world (World object):
                The object representing the world this thing exists in.

            name (str):
                Name of the thing.
        '''

        data_dir = world.get_element_dir(
            name,
            'things',
            subdirs = resides_in,
            element_type_ind = -1,
        )
        filename = world.get_element_timeline_filename( name )
        
        tl = super( Thing, cls ).load( data_dir, filename )
        c = Thing(
            world = world,
            name = name,
            data = tl.data,
            **tl.params
        )

        return c
