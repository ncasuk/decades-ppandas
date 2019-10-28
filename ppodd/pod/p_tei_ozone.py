import numpy as np

from ..decades import DecadesVariable, DecadesBitmaskFlag
from ..decades import flags
from .base import PPBase

class TeiOzone(PPBase):

    inputs = [
        'TEIOZO_conc',
        'TEIOZO_flag',
        'TEIOZO_FlowA',
        'TEIOZO_FlowB',
        'WOW_IND'
    ]

    def declare_outputs(self):

        self.declare(
            'O3_TECO',
            units='ppb',
            frequency=1,
            number=574,
            long_name=('Mole fraction of Ozone in air from the TECO 49 '
                       'instrument'),
            standard_name='mole_fraction_of_ozone_in_air'
        )

    def flag(self):
        FLOW_THRESHOLD = 0.5
        CONC_THRESHOLD = -10
        FLAG_AFTER_TO = 20

        d = self.d

        d['STATUS_FLAG'] = 0
        d['STATUS_FLAG1'] = 0
        d['STATUS_FLAG2'] = 0

        d['CONC_FLAG'] = 0
        d['FLOW_FLAG'] = 0
        d['WOW_FLAG'] = 0

        d['TEIOZO_flag'].fillna(value='', inplace=True)
        flag = np.array([i.lower() for i in d['TEIOZO_flag']])
        flag[flag == ''] = 3

        if '1c100000' in flag:
            d.STATUS_FLAG1 = flag != '1c100000'

        if '0c100000' in flag:
            d.STATUS_FLAG2 = flag != '0c100000'

        d.STATUS_FLAG = d.STATUS_FLAG1 | d.STATUS_FLAG2

        d.loc[d['TEIOZO_conc'] < CONC_THRESHOLD, 'CONC_FLAG'] = 1
        d.loc[d['TEIOZO_FlowA'] < FLOW_THRESHOLD, 'FLOW_FLAG'] = 1
        d.loc[d['TEIOZO_FlowB'] < FLOW_THRESHOLD] = 1
        d.loc[d['WOW_IND'] != 0, 'WOW_FLAG'] = 1

    def process(self):
        self.get_dataframe()

        self.flag()

        dv = DecadesVariable(self.d['TEIOZO_conc'], name='O3_TECO',
                             flag=DecadesBitmaskFlag)

        dv.flag.add_mask(self.d['STATUS_FLAG'], 'instrument_alarm')
        dv.flag.add_mask(self.d['CONC_FLAG'], 'conc_out_of_range')
        dv.flag.add_mask(self.d['FLOW_FLAG'], 'flow_out_of_range')
        dv.flag.add_mask(self.d['WOW_FLAG'], flags.WOW)

        self.add_output(dv)
