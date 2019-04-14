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

########################################################################
########################################################################

class Character( object ):

    @utilities.store_parameters
    def __init__(
        self,
        char_dir,
    ):
        pass

    ########################################################################

    @classmethod
    def from_generated_character( cls, char_dir, gen_char ):
        '''Retrieve from a generated character.'''

        c = cls( char_dir )

        # Copy personality traits and quirks
        c.personality_traits = {}
        c.personality_traits['pos_traits'] = gen_char.pos_traits
        c.personality_traits['neg_traits'] = gen_char.neg_traits
        c.personality_traits['quirks'] = gen_char.quirks
        c.personality_traits = pd.Series( c.personality_traits )

        # Copy physical traits
        c.physical_traits = {}
        c.physical_traits['eye_color'] = gen_char.eye_color
        c.physical_traits['hair_color'] = gen_char.hair_color
        c.physical_traits['skin_tone'] = gen_char.skin_tone
        c.physical_traits['height'] = gen_char.height
        c.physical_traits = pd.Series( c.physical_traits )

        return c

    ########################################################################

