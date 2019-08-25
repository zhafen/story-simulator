#!/usr/bin/env python
'''Objects and function for creating and dealing with settings

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

class Setting( timeline.Timeline ):

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
        resides_in = [],
        **kwargs
    ):

        super( Setting, self ).__init__(
            data_dir = world.get_element_dir(
                name,
                'settings',
                subdirs = resides_in,
            ),
            filename = world.get_element_timeline_filename( name ),
            **kwargs
        )

        self.action_queue = queue.Queue()

    ########################################################################
    # Constructors
    ########################################################################

    # @classmethod
    # def from_generated_setting( cls, gen_char, t ):
    #     '''Retrieve from a generated setting.'''

    #     c = Setting(
    #         world = gen_char.world,
    #         name = gen_char.data['name'],
    #         data = {},
    #         t_update = t,
    #     )
    #     c.store_state( gen_char.data, t )

    #     return c

    ########################################################################

    @classmethod
    def load( cls, world, name, resides_in=[] ):
        '''Load a setting from an existing file.

        Args:
            world (World object):
                The object representing the world this setting exists in.

            name (str):
                Name of the setting.
        '''

        data_dir = world.get_element_dir(
            name,
            'settings',
            subdirs = resides_in,
        )
        filename = world.get_element_timeline_filename( name )
        
        tl = super( Setting, cls ).load( data_dir, filename )
        c = Setting(
            world = world,
            name = name,
            data = tl.data,
            **tl.params
        )

        return c

    ########################################################################

    @property
    def contained_settings( self ):
        '''Names of the settings inside this setting.
        '''

        if not hasattr( self, '_contained_settings' ):

            # List items
            ls = os.listdir( self.data_dir )

            # Select only contained settings, and get names
            self._contained_settings = []
            for item in ls:

                # Skip non-settings
                filepath = os.path.join( self.data_dir, item )
                if not os.path.isdir( filepath ):
                    continue

                name = item.replace( '_', ' ' )

                self._contained_settings.append( name )

        return self._contained_settings
