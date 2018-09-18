import numpy as np

from ..decades import DecadesVariable
from ..utils.calcs import sp_mach
from ..utils.constants import SPEED_OF_SOUND, ICAO_STD_TEMP, ICAO_STD_PRESS
from .base import PPBase

class AirSpeed(PPBase):

    inputs = [
        'TASCORR',          #  Airspeed correction factor (const)
        'PS_RVSM',          #  Static Pressure (derived)
        'Q_RVSM',           #  Pitot-static pressure (derived)
        'TAT_DI_R'          #  Deiced true air temp (derived)
    ]

    def declare_outputs(self):

        self.declare(
            'IAS_RVSM',
            units='m s-1',
            frequency=32,
            number=516,
            long_name=('Indicated air speed from the aircraft RVSM '
                       '(air data) system')
        )

        self.declare(
            'TAS_RVSM',
            units='m s-1',
            frequency=32,
            number=517,
            long_name=('True air speed from the aircraft RVSM (air data) '
                       'system and deiced temperature'),
            standard_name='platform_speed_wrt_air'
        )

    def calc_ias(self):
        d = self.d

        ias = (SPEED_OF_SOUND * d['MACHNO'] *
               np.sqrt(d['PS_RVSM'] / ICAO_STD_PRESS))

        d['IAS_RVSM'] = ias

    def calc_tas(self):
        d = self.d

        tas = (
            self.dataset['TASCORR']
            * SPEED_OF_SOUND
            * d['MACHNO']
            * np.sqrt(d['TAT_DI_R'] / ICAO_STD_TEMP)
        )

        d['TAS_RVSM'] = tas

    def calc_mach(self):
        d = self.d

        d['MACHNO'], d['MACHNO_FLAG'] = sp_mach(
            d['Q_RVSM'], d['PS_RVSM'], flag=True
        )

    def process(self):
        self.get_dataframe()

        self.calc_mach()
        self.calc_ias()
        self.calc_tas()

        ias = DecadesVariable(self.d['IAS_RVSM'])
        tas = DecadesVariable(self.d['TAS_RVSM'])

        for _var in (ias, tas):
            _var.add_flag(self.d['MACHNO_FLAG'])
            self.add_output(_var)
