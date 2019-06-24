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
    # Properties
    ########################################################################

    @property
    def pos_traits( self ):

        return utilities.generic_table_getter(
            self,
            'pos_traits',
            self.char_dir,
            subfolders = [ 'data', ],
        )

    @pos_traits.setter
    def pos_traits( self, value ):

        return utilities.generic_table_setter(
            self,
            'pos_traits',
            value,
            self.char_dir,
            subfolders = [ 'data', ],
        )

    ########################################################################

    @property
    def neg_traits( self ):

        return utilities.generic_table_getter(
            self,
            'neg_traits',
            self.char_dir,
            subfolders = [ 'data', ],
        )

    @neg_traits.setter
    def neg_traits( self, value ):

        return utilities.generic_table_setter(
            self,
            'neg_traits',
            value,
            self.char_dir,
            subfolders = [ 'data', ],
        )

    ########################################################################
    
    @property
    def quirks( self ):

        return utilities.generic_table_getter(
            self,
            'quirks',
            self.char_dir,
            subfolders = [ 'data', ],
        )

    @quirks.setter
    def quirks( self, value ):

        return utilities.generic_table_setter(
            self,
            'quirks',
            value,
            self.char_dir,
            subfolders = [ 'data', ],
        )

    ########################################################################
    
    @property
    def physical_traits( self ):

        return utilities.generic_table_getter(
            self,
            'physical_traits',
            self.char_dir,
            subfolders = [ 'data', ],
        )

    @physical_traits.setter
    def physical_traits( self, value ):

        return utilities.generic_table_setter(
            self,
            'physical_traits',
            value,
            self.char_dir,
            subfolders = [ 'data', ],
        )

    ########################################################################

    @classmethod
    def from_generated_character( cls, char_dir, gen_char ):
        '''Retrieve from a generated character.'''

        c = cls( char_dir )

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

