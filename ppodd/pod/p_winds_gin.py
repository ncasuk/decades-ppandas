import pandas as pd
import numpy as np

from ..decades import DecadesVariable, DecadesBitmaskFlag
from .base import PPBase
from .shortcuts import _o, _z

ROLL_THRESH = 2


class GINWinds(PPBase):

    inputs = [
        'GIN_HDG_OFFSET',
        'VELE_GIN',
        'VELN_GIN',
        'HDG_GIN',
        'TAS_RVSM',
        'ROLL_GIN',
        'TAT_DI_R'
    ]

    @staticmethod
    def test():
        return {
            'GIN_HDG_OFFSET': ('const', 0),
            'VELE_GIN': ('data', 100 * _o(100)),
            'VELN_GIN': ('data', 100 * _o(100)),
            'HDG_GIN': ('data', _z(100)),
            'TAS_RVSM': ('data', 130 * _o(100)),
            'ROLL_GIN': ('data', _z(100)),
            'TAT_DI_R': ('data', 250 * _o(100))
        }

    def declare_outputs(self):
        self.declare(
            'U_NOTURB',
            units='m s-1',
            frequency=1,
            long_name=('Eastward wind component derived from aircraft '
                       'instruments and GIN'),
            standard_name='eastward_wind'
        )

        self.declare(
            'V_NOTURB',
            units='m s-1',
            frequency=1,
            long_name=('Northward wind component derived from aircraft '
                       'instruments and GIN'),
            standard_name='northward_wind'
        )

    def correct_tas_rvsm(self, tas_scale_factor=1):
        """
        Correct TAS from the RVSM ADC to match the radome probe. The reference
        for this is AW's lab book. TODO: those docs need porting across, though
        currently unclear that we should actually be doing this.

        Kwargs:
            tas_scale_factor: a scaling factor for TAS to minimise reverse
            heading errors.
        """
        d = self.d

        dit = self.d.TAT_DI_R

        mach = d.TAS_RVSM / (661.4788 * 0.514444) / np.sqrt(dit / 288.15)
        delta_tas = 4.0739 - (32.1681 * mach) + (52.7136 * (mach**2))
        d['TAS'] = (d.TAS_RVSM - delta_tas) * tas_scale_factor

    def calc_noturb_wspd(self):
        """
        Calculate the noturb u and v wind components,  as the difference
        between the iargraft ground and air vectors.
        """
        d = self.d

        try:
            tas_scale_factor = self.dataset['GINWIND_TASCOR']
        except KeyError:
            # No GINWIND_TASCOR
            tas_scale_factor = 1

        # Apply a correction to the RVSM TAS
        self.correct_tas_rvsm(tas_scale_factor=tas_scale_factor)

        d.HDG_GIN += self.dataset['GIN_HDG_OFFSET']
        air_spd_east = np.cos(np.deg2rad(d.HDG_GIN - 90.)) * d.TAS
        air_spd_north = np.sin(np.deg2rad(d.HDG_GIN - 90.)) * d.TAS

        d['U_NOTURB'] = d.VELE_GIN - air_spd_east
        d['V_NOTURB'] = d.VELN_GIN + air_spd_north

    def process(self):
        """
        Processing entry point.
        """
        start_time = self.dataset['TAS_RVSM'].index[0].round('1S')
        end_time = self.dataset['TAS_RVSM'].index[-1].round('1S')

        self.get_dataframe(
            method='onto',
            index=pd.date_range(start=start_time, end=end_time, freq='1S'),
            circular=['HDG_GIN'], limit=50
        )

        self.correct_tas_rvsm()
        self.calc_noturb_wspd()

        u = DecadesVariable(self.d.U_NOTURB, flag=DecadesBitmaskFlag)
        v = DecadesVariable(self.d.V_NOTURB, flag=DecadesBitmaskFlag)

        for var in (u, v):
            var.flag.add_mask(
                self.d.ROLL_GIN.abs() > ROLL_THRESH,
                'roll exceeds threshold'
            )

            self.add_output(var)

