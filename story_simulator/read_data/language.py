#!/usr/bin/env python
'''Functions for generating names.

@author: Zach Hafen
@contact: zachary.h.hafen@gmail.com
@status: Development
'''

import copy
import numpy as np
import os
import pandas as pd

import story_simulator

import hoard.utils.utilities as utilities

########################################################################
########################################################################

class LanguageDataReader( object ):

    @utilities.store_parameters
    def __init__(
        self,
        phonemes = None,
        phonemes_dir = None,
    ):
        '''Constructor.

        Args:
            phonemes (str or array-like) :
                List of phonemes to use.

            phonemes_dir (str) :
                The directory the phonemes data is stored in. Defaults to the
                directory this file is stored in.
        '''

        if phonemes_dir is None:
            package_path = os.path.dirname(
                os.path.realpath( story_simulator.__file__ )
            )
            self.phonemes_dir = os.path.join(
                package_path,
                'data',
            )

    ########################################################################
    # Properties
    ########################################################################

    @property
    def phonemes_table( self ):
        '''Data used to create words.'''

        return utilities.generic_table_getter(
            self,
            property_name = 'phonemes_table',
            root_folder = self.phonemes_dir,
            index_col = 0,
        )

    ########################################################################

    @property
    def vowels( self ):
        return self.phonemes_table.loc[self.phonemes_table['Vowel']]

    @property
    def consonants( self ):
        return self.phonemes_table.loc[
            np.invert(self.phonemes_table['Vowel'])
        ]

    ########################################################################

    @property
    def available_phonemes( self ):
        '''Actual data used'''

        if self.phonemes is None:
            return self.phonemes_table

        # Case where particular phonemes are selected
        else:
            if not hasattr( self, '_available_phonemes' ):
                self._available_phonemes = \
                    self.phonemes_table.loc[self.phonemes]
            return self._available_phonemes

    ########################################################################

    @property
    def available_vowels( self ):
        return self.available_phonemes.loc[self.available_phonemes['Vowel']]

    @property
    def available_consonants( self ):
        return self.available_phonemes.loc[
            np.invert(self.available_phonemes['Vowel'])
        ]

