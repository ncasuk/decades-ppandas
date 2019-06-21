import numpy as np
import pandas as pd

from pysolar.solar import get_altitude, get_azimuth

from ..decades import DecadesVariable
from .base import PPBase


class SolarAngles(PPBase):

    inputs = [
        'LAT_GIN',
        'LON_GIN'
    ]

    def declare_outputs(self):
        self.declare(
            'SOL_AZIM',
            units='degree',
            frequency=1,
            number=642,
            long_name='Solar azimuth derived from aircraft position and time',
            standard_name='solar_azimuth_angle'
        )

        self.declare(
            'SOL_ZEN',
            units='degree',
            frequency=1,
            number=643,
            long_name='Solar zenith derived from aircraft position and time',
            standard_name='solar_zenith_angle'
        )

    def process(self):
        """
        Processing entry point.
        """

        start = self.dataset[self.inputs[0]].index[0].round('1S')
        end = self.dataset[self.inputs[0]].index[-1].round('1S')
        index = pd.date_range(start, end, freq='1S')
        index_utc = pd.date_range(start, end, freq='1S',
                                  tz='utc').to_pydatetime()

        self.get_dataframe(method='onto', index=index)

        lats = self.d.LAT_GIN
        lons = self.d.LON_GIN

        vector_zen = np.vectorize(lambda x, y, t: get_altitude(x, y, t))
        vector_azi = np.vectorize(lambda x, y, t: get_azimuth(x, y, t))

        zenith = pd.Series(90 - vector_zen(lats, lons, index_utc), index=index)
        azimuth = pd.Series(vector_azi(lats, lons, index_utc), index=index)

        self.add_output(DecadesVariable(zenith, name='SOL_ZEN'))
        self.add_output(DecadesVariable(azimuth, name='SOL_AZIM'))
