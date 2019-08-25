#!/usr/bin/env python
'''Objects and function for creating and dealing with characters.

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

########################################################################
########################################################################

class World( object ):

    @utilities.store_parameters
    def __init__(
        self,
        world_dir,
    ):
        pass

    ########################################################################
    # Properties
    ########################################################################

    # @property
    # def historical_events( self ):

    #     return utilities.generic_table_getter(
    #         self,
    #         'historical_events',
    #         self.world_dir,
    #         subfolders = [ 'world' ]
    #     )

    ########################################################################

    # @property
    # def events( self ):

    #     return utilities.generic_table_getter(
    #         self,
    #         'events',
    #         self.world_dir,
    #         subfolders = [ 'world' ]
    #     )

    ########################################################################

    # @property
    # def languages( self ):

    #     return utilities.generic_table_getter(
    #         self,
    #         'languages',
    #         self.world_dir,
    #         subfolders = [ 'world', 'languages' ]
    #     )

    # @languages.setter
    # def languages( self, value ):
    #     utilities.generic_table_setter(
    #         self,
    #         'languages',
    #         value,
    #         self.world_dir,
    #         subfolders = [ 'world', 'languages' ]
    #     )

    ########################################################################

    # @property
    # def characters( self ):

    #     return utilities.generic_table_getter(
    #         self,
    #         'characters',
    #         self.world_dir,
    #         subfolders = [ 'world', 'characters' ]
    #     )

    ########################################################################

    # @property
    # def nodes( self ):

    #     return utilities.generic_table_getter(
    #         self,
    #         'nodes',
    #         self.world_dir,
    #         subfolders = [ 'world', 'settings' ]
    #     )

    ########################################################################

    # @property
    # def magic_archetypes( self ):

    #     return utilities.generic_table_getter(
    #         self,
    #         'archetypes',
    #         self.world_dir,
    #         subfolders = [ 'world', 'magic' ]
    #     )

    ########################################################################
    # File Management
    ########################################################################

    def get_element_dir( self, name, element_type, subdirs=[] ):
        '''Get the directory a story element's data is stored in.

        Args:
            name (str):
                Name of the element. Can have slashes indicating
                separate directories.

            element_type (str): Name of the type of object the element is.

            subdirs (list of strs): Subdirectories within the element type.

        Returns:
            str:
                Directory containing the data for the element.
        '''

        # Copies to avoid altering the originals
        used_name = copy.copy( name )
        used_subdirs = copy.copy( subdirs )

        # See if the name is pointing at a path
        split_name = used_name.split( '/' )

        # Extend the subdir list if appropriate
        if len( split_name ) > 1:

            # Split the name up
            used_name = split_name[-1]
            used_subdirs += split_name[:-1]

            # Make sure formatting is correct
            used_subdirs = [ x.replace( ' ', '_' ) for x in used_subdirs ]

        if len( used_subdirs ) == 0:
            result = os.path.join(
                self.world_dir,
                'world',
                element_type,
                used_name
            )
        else:
            subdirs_str = os.path.join( *used_subdirs )
            result = os.path.join(
                self.world_dir,
                'world',
                element_type,
                subdirs_str,
                used_name
            )

        return result.replace( ' ', '_' )

    ########################################################################

    def get_element_timeline_filename( self, name ):
        '''Get the filename for a story element's timeline.

        Args:
            name (str): Name of the element.

        Returns:
            str:
                Filename for the timeline data.
        '''

        # If the name is given as part of a directory, split it up
        name = name.split( '/' )[-1]

        return '{}.tld'.format( name.replace( ' ', '_' ) )

    ########################################################################
    # Methods
    ########################################################################

    # def sample_part( self, part_name, n_samples=1 ):

    #     part = getattr( self, part_name )

    #     ind = prob_tools.sample_discrete_probabilities(
    #         part['Likelihood'].values,
    #         normalize = True
    #     )

    #     if n_samples == 1:
    #         return part.loc[ind]
    #     else:
    #         raise Exception( "Multiple samples not implemented yet." )
