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

    ########################################################################

    @classmethod
    def from_generated_character( cls, char_dir, gen_char ):
        '''Retrieve from a generated character.'''

        assert False, 'Fix this.'

        # Copy and save personality traits and quirks
        c.pos_traits = gen_char.pos_traits
        c.neg_traits = gen_char.neg_traits
        c.quirks = gen_char.quirks

        # Copy physical traits
        physical_traits = {}
        physical_traits['eye_color'] = gen_char.eye_color
        physical_traits['hair_color'] = gen_char.hair_color
        physical_traits['skin_tone'] = gen_char.skin_tone
        physical_traits['height'] = gen_char.height
        c.physical_traits = pd.Series( physical_traits )

        return c

    ########################################################################

