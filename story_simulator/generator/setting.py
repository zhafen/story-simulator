#!/usr/bin/env python
'''Code for generating characters.

@author: Zach Hafen
@contact: zachary.h.hafen@gmail.com
@status: Development
'''

import copy
import numpy as np
import os
import pandas as pd

import hoard.utils.utilities as utilities
import hoard.utils.probability_tools as prob_tools

import story_simulator.language as language
import story_simulator.config as ss_config
import story_simulator.utils.utils as utils
import story_simulator.generator.utils as gen_utils

########################################################################
########################################################################

class GeneratedSetting( object ):

    @utilities.store_parameters
    def __init__(
        self,
        world,
        data_dir = ss_config.DATA_DIR,
    ):
        '''Constructor.

        Args:
            world (object):
                The world this is being constructed for.

            data_dir (str):
                Where the data used to generate characters is stored.
                Defaults to the story_simulator overall data dir
        '''

        pass

    ########################################################################
    # Methods
    ########################################################################

    def generate_name( self, language_name=None, **kwargs ):

        if language_name is not None:
            l = language.Language( language_name, self.world, )
        else:
            l = None

        self.name = gen_name.Name( language=l, **kwargs )

        print( 'Name = {}'.format( self.name ) )

    ########################################################################

    def save( self, char_dir ):

        char = character.Character.from_generated_character( char_dir, self )

        return char
