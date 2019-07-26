#!/usr/bin/env python
'''Objects and function for creating and dealing with characters.

@author: Zach Hafen
@contact: zachary.h.hafen@gmail.com
@status: Development
'''

import numpy as np
import os
import pandas as pd

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
        **kwargs
    ):

       super( Character, self ).__init__(
            data_dir = world.get_character_dir( name ),
            filename = world.get_character_timeline_filename( name ),
            **kwargs
        )

    ########################################################################

    @classmethod
    def from_generated_character( cls, gen_char, t ):
        '''Retrieve from a generated character.'''

        c = Character(
            world = gen_char.world,
            name = gen_char.data['name'],
            data = {},
        )

        #DEBUG
        import pdb; pdb.set_trace()
        c.store_state( gen_char.data, t )

        return c

    ########################################################################

