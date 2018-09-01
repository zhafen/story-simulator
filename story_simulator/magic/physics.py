#!/usr/bin/env python
'''Functions for calculating physics quantities
(necessary for understanding magic).

@author: Zach Hafen
@contact: zachary.h.hafen@gmail.com
@status: Development
'''

import unyt
import numpy as np

########################################################################
########################################################################

def kinetic_energy( mass, speed ):
    '''Standard simple kinetic energy.

    Args:
        mass (unyt array or quantity) :
            Mass of object

        speed (unyt array or quantity) :
            Magnitude of velocity.
    '''

    ke = mass * speed**2.

    return ke.to( 'J' )

########################################################################

def thermal_energy( mass, temperature ):
    '''Estimate for thermal energy given as n * k_B * T

    Args:
        mass (unyt array or quantity) :
            Mass of object

        temperature (unyt array or quantity) :
            Temperature of object
    '''

    n = mass / unyt.mass_hydrogen

    temp = temperature.to( 'K' )

    te = n * temp.to( 'J', equivalence='thermal' )

    return te

########################################################################

def temp_change_to_energy( mass, final_temp, initial_temp, medium='air', ):
    '''Energy needed to heat a substance.
    '''

    specific_heat_capacities = {
        'air' : 1.012,
        'water' : 4.1813,
    }
    s = specific_heat_capacities[medium] * unyt.J / unyt.g / unyt.K

    dtemp = ( final_temp - initial_temp ).to( 'K' )

    return ( mass * dtemp * s ).to( 'J' )

########################################################################

def gravitational_energy( mass1, mass2, distance ):
    '''Estimate the gravitational energy between two objects

    Args:
        mass1, mass2 (unyt array or quantity) :
            Mass of object 1 and 2

        distance (unyt array or quantity) :
            Distance to object
    '''

    pe = -1. * unyt.G * mass1 * mass2 / distance

    return pe.to( 'J' )


