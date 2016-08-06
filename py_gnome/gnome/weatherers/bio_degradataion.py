﻿'''
model biodegradation process
'''
import numpy as np

from gnome.utilities.serializable import Serializable

from .core import WeathererSchema
from gnome.weatherers import Weatherer

from gnome.array_types import (mass, 
                               droplet_avg_size)

from math import exp, pi

class Biodegradation(Weatherer, Serializable):
    _state = copy.deepcopy(Weatherer._state)
    _schema = WeathererSchema

    def __init__(self, **kwargs):

        self.comp_masses_at_time0 = None

        super(Biodegradation, self).__init__(**kwargs)

        self.array_types.update({'mass':  mass,
                                 'droplet_avg_size': droplet_avg_size
                                 })


    def prepare_for_model_run(self, sc):
        '''
            Add biodegradation key to mass_balance if it doesn't exist.
            - Assumes all spills have the same type of oil
            - let's only define this the first time
        '''
        if self.on:
            super(Biodegradation, self).prepare_for_model_run(sc)
            sc.mass_balance['bio_degradation'] = 0.0

            # we need initial psedocomponent masses for further calculations
            self.comp_masses_at_time0 = sc['mass_components']


    def prepare_for_model_step(self, sc, time_step, model_time):
        '''
            Set/update arrays used by bio degradation module for this timestep
        '''
        super(Biodegradation, self).prepare_for_model_step(sc, time_step, model_time)

        if not self.active:
            return


    def bio_degradate_oil(self, data, substance, **kwargs):
        '''
            Calculate oil bio degradation
            1. Droplet distribution per LE should be calculated by the natural
            dispersion process and saved in the data arrays before the 
            biodegradation weathering process.
            2. Biodegradation rate coefficients are calculated for temperate or arctic
            emvironment conditions - set in parameter 'arctic': True/False.
            3. It must take into consideration saturates below C30 and aromatics only.
            4. It uses pseudo component boiling point to select rate constant
         '''

        comp_masses = data['mass_components']
        droplet_avg_sizes = data['droplet_avg_size']

        # we are going to calculate bio degradation rate coefficients (K_comp_rates) just
        # for saturates below C30 and aromatics components - other ones are masked to 0.0

        assert 'boiling_point' in substance._sara.dtype.names
        type_bp = substance._sara[['type','boiling_point']]

        if 'arctic' not in kwargs:
            arctic = False

        K_comp_rates = np.array(map(get_K_comp_rates, type_bp, arctic))

        # 
        mass_biodegradated = comp_masses_at_time0 * exp(-pi * droplet_avg_sizes ** 2 *   # droplet_avg_sizes - droplet diameter?
                                                        K_comp_rates / comp_masses.sum(axes=1))

        return mass_biodegradated

    def get_K_comp_rates(self, type_and_bp, arctic = False):
        '''
            Get bio degradation rate coefficient based on component type and 
            its boiling point for temparate or arctic environment conditions
            :param type_and_bp - a tuple ('type', 'boiling_point')
                - 'type': component type, string
                - 'boiling_point': float value
            :param boolean arctic = False - flag for arctic conditions (below 6 deg C)
        '''

        if type_and_bp[0] == 'Saturates':
            if type_and_bp[1] < 722.85:     # 722.85 - boiling point for C30 saturate (K)
                return 0.128807242 if arctic else 0.941386396
            else:
                return 0.0                  # zero rate for C30 and above saturates

        elif type_and_bp[1] == 'Aromatics':
            if type_and_bp[1] < 630.0:      # 
                return 0.126982603 if arctics else 0.575541103
            else:
                return 0.021054707 if arctics else 0.084840485
        else:
            return 0.0                      # zero rate for ather than saturates and aromatics
        

    def weather_elements(self, sc, time_step, model_time):
        '''
            weather elements over time_step
        '''
        if not self.active:
            return

        if sc.num_released == 0:
            return

        for substance, data in sc.itersubstancedata(self.array_types):
            if len(data['mass']) is 0:
                # data does not contain any surface_weathering LEs
                continue

            # calculate the mass over time step
            bio_deg = self.bio_degradate_oil(data=data,
                                             substance=substance)

            # calculate mass ballance for bio degradation process - mass loss
            sc.mass_balance['bio_degradation'] += data['mass'] - bio_deg.sum(1)

            # update masses
            data['mass_components'] = bio_deg
            data['mass'] = data['mass_components'].sum(1)

            # log bio degradated amount
            self.logger.debug('{0} Amount bio degradated for {1}: {2}'
                              .format(self._pid,
                                      substance.name,
                                      sc.mass_balance['bio_degradation']))

        sc.update_from_fatedataview()


    def serialize(self, json_='webapi'):

        toserial = self.to_serialize(json_)
        schema = self.__class__._schema()
        serial = schema.serialize(toserial)

        return serial

    @classmethod
    def deserialize(cls, json_):
 
        if not cls.is_sparse(json_):
            schema = cls._schema()
            dict_ = schema.deserialize(json_)
            return dict_
        else:
            return json_