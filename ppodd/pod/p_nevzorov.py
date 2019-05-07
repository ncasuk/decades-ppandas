import numpy as np

from scipy.optimize import curve_fit

from ..decades import DecadesVariable
from .base import PPBase


def get_no_cloud_mask(twc_col_p, wow, window_secs=3, min_period=5, freq=64):
    """
    Create a mask giving times when we are
    a) in clear air
    b) not on the ground.
    This is determined by looking at the range of the total water collector
    power in a given window. Range in cloud should be significantly higher than
    the range in clear air.

    Args:
        twc_col_p: Total Water Collector power, as a pd.Series.
        wow: The weighton-wheels flag

    Kwargs:
        window_secs: the size of the window, in secs
        min_period: the minimum total time, in secs, that we must be in/out of
                    cloud to flip the flag value.
        freq: The frequency of the Nevzorov signal.

    Returns:
        mask: The clear air mask. 1 indicates inflight/no cloud, 0 indicates on
              ground/in cloud.
    """

    range_limits = (1E-12, 0.1)

    def _roll_fn(arr):
        """
        Reduce an array to a flag, based on its range.

        Args:
            arr: the array to produce a flag value

        Returns:
            a flag value of 0 or 1
        """
        _range = np.ptp(arr)
        return range_limits[0] < _range < range_limits[1]

    # Generate mask by looking at range in a rollinf window
    mask = twc_col_p.rolling(
        freq * window_secs, center=True
    ).apply(_roll_fn, raw=True)

    # Flag as 0 when on the ground
    mask.loc[wow == 1 | np.isnan(wow)] = 0

    # Ensure each segment is long enough
    mask_groups = (mask != mask.shift()).cumsum()
    for group in mask_groups.unique():
        if mask.loc[mask_groups == group].sum() < min_period * freq:
            mask.loc[mask_groups == group] = 0

    return mask


def get_fitted_k(col_p, ref_p, ias, ps, no_cloud_mask, k):
    """
    The Nevzorov baseline is not constant, but varies as a function of
    indicated air speed (IAS_RVSM) and static air pressure (PS_RVSM).
    Abel et al. (2014) provide a fitting formula in Appendix A to correct
    the K value (ratio between collector and reference power, when outside of
    clouds) to remove the zero offset of the liquid and total water
    measurements.

    Reference:
        S J Abel, R J Cotton, P A Barrett and A K Vance. A comparison of ice
        water content measurement techniques on the FAAM BAe-146 aircraft.
        Atmospheric Measurement Techniques 7(5):4815--4857, 2014.

    Args:
        col_p: Nevz. collector power (W), pd.Series
        ref_p: Nevz. reference power (W), pd.Series
        ias: Indicated airspeed (m s-1), pd.Series
        ps: Static Pressure (hPa), pd.Series
        no_cloud_mask: mask indicating in (0) or out (1) of cloud, pd.Series
        k: K value given in the flight constants.

    Returns:
        a tuple (K, A), where K is the fitted K value (pd.Series) and A is a
        tuple containing the fit parameters.

    """

    def fit_func(x, a, b):
        """
        (col_pow / ref_pow) - k - [ a(1/ias) + b log_10(Ps) ]
        """
        return (
            x[0, :] / x[1, :] - k - (a * (1 / x[2, :]) + b * np.log10(x[3, :]))
        )

    xdata = np.vstack([
        col_p.loc[no_cloud_mask == 1].values,
        ref_p.loc[no_cloud_mask == 1].values,
        ias.loc[no_cloud_mask == 1].values,
        ps.loc[no_cloud_mask == 1].values
    ])

    popt, pcov = curve_fit(fit_func, xdata, xdata[0, :] * 0.0)

    return (k + (popt[0] * (1. / ias) + popt[1] * np.log10(ps)), popt)


class Nevzorov(PPBase):
    """
    Post processing for liquid and total water from the Nevzorov Vane. Works
    with both 1T1L2R and 1T2L1R vanes, which should be specified in the
    flight constants as VANETYPE.
    """

    inputs = [
        'CORCON_nv_lwc_vcol',
        'CORCON_nv_lwc_icol',
        'CORCON_nv_lwc_vref',
        'CORCON_nv_lwc_iref',
        'CORCON_nv_twc_vcol',
        'CORCON_nv_twc_icol',
        'CORCON_nv_twc_vref',
        'CORCON_nv_twc_iref',
        'TAS_RVSM',
        'IAS_RVSM',
        'PS_RVSM',
        'WOW_IND',
        'CLWCIREF', 'CLWCVREF', 'CLWCICOL',
        'CLWCVCOL',
        'CTWCIREF', 'CTWCVREF', 'CTWCICOL',
        'CTWCVCOL',
        'CALNVTWC',
        'CALNVLWC1',
        'CALNVLWC2',
        'CALNVL'
    ]

    instruments = {
        '1t1l2r': ('twc', 'lwc'),
        '1t2l1r': ('twc', 'lwc1', 'lwc2')
    }

    def _declare_outputs_common(self):
        """
        Declare the outputs that are common between both Nevz. vanes.
        """

        self.declare(
            'NV_TWC_U',
            units='gram m-3',
            frequency=64,
            number=605,
            long_name=('Uncorrected total condensed water content from the '
                       'Nevzorov probe')
        )

        self.declare(
            'NV_TWC_C',
            units='gram m-3',
            frequency=64,
            number=609,
            long_name=('Corrected total condensed water content from the '
                       'Nevzorov probe')
        )

        self.declare(
            'NV_TWC_COL_P',
            units='W',
            frequency=64,
            long_name='TWC collector power'
        )

    def _declare_outputs_1t1l2r(self):
        """
        Declare the outputs that are only valid for the 1t1l2r vane type
        """

        self.declare(
            'NV_LWC_U',
            units='gram m-3',
            frequency=64,
            number=602,
            long_name=('Uncorrected liquid water content from the Nevzorov '
                       'probe'),
            standard_name='mass_concentration_of_liquid_water_in_air'
        )

        self.declare(
            'NV_LWC_C',
            units='gram m-3',
            frequency=64,
            number=608,
            long_name='Corrected liquid water content from the Nevzorov probe',
            standard_name='mass_concentration_of_liquid_water_in_air'
        )

        self.declare(
            'NV_TWC_REF_P',
            units='W',
            frequency=64,
            long_name='TWC reference power'
        )

        self.declare(
            'NV_LWC_COL_P',
            units='W',
            frequency=64,
            long_name='LWC collector power'
        )

        self.declare(
            'NV_LWC_REF_P',
            units='W',
            frequency=64,
            long_name='LWC reference power'
        )

    def _declare_outputs_1t2l1r(self):
        """
        Declare the outputs that are only valid for the 1t2l1r vane type.
        """

        self.declare(
            'NV_LWC1_U',
            units='gram m-3',
            frequency=64,
            number=602,
            long_name=('Uncorrected liquid water content from the Nevzorov '
                       'probe (1st collector)'),
            standard_name='mass_concentration_of_liquid_water_in_air'
        )

        self.declare(
            'NV_LWC1_C',
            units='gram m-3',
            frequency=64,
            number=608,
            long_name=('Corrected liquid water content from the Nevzorov probe'
                       ' (1st collector)'),
            standard_name='mass_concentration_of_liquid_water_in_air'
        )

        self.declare(
            'NV_LWC2_U',
            units='gram m-3',
            frequency=64,
            number=602,
            long_name=('Uncorrected liquid water content from the Nevzorov '
                       'probe (2nd collector)'),
            standard_name='mass_concentration_of_liquid_water_in_air'
        )

        self.declare(
            'NV_LWC2_C',
            units='gram m-3',
            frequency=64,
            number=608,
            long_name=('Corrected liquid water content from the Nevzorov probe'
                       ' (2nd collector)'),
            standard_name='mass_concentration_of_liquid_water_in_air'
        )

        self.declare(
            'NV_REF_P',
            units='W',
            frequency=64,
            long_name='Reference power'
        )

        self.declare(
            'NV_LWC1_COL_P',
            units='W',
            frequency=64,
            long_name='LWC1 collector power'
        )

        self.declare(
            'NV_LWC2_COL_P',
            units='W',
            frequency=64,
            long_name='LWC2 collector power'
        )

    def declare_outputs(self):
        """
        Declare the module outputs, which are dependent on the type of vane
        fitted to the aircraft.
        """

        self._declare_outputs_common()

        _vanetype = self.dataset['VANETYPE'].lower()

        if _vanetype == '1t1l2r':
            self._declare_outputs_1t1l2r()
        elif _vanetype == '1t2l1r':
            self._declare_outputs_1t2l1r()
        else:
            raise ValueError(
                'Unknown Nevz. vane type: {}'.format(_vanetype)
            )

    def _remap_1t2l1r(self):
        """
        The variables in DECADES are named for the old Nevzorov vane type,
        which had 1 total, 1 liquid and 2 reference sensors. When running with
        the new vane type, which has 1 total, 2 liquid and 1 reference sensors,
        we need to map the old variable names onto new ones which correspont to
        the new vane design.
        """

        _vanetype = self.dataset['VANETYPE'].lower()

        if _vanetype != '1t2l1r':
            return

        var_map = (
            ('CORCON_nv_lwc1_vcol', 'CORCON_nv_lwc_vcol'),
            ('CORCON_nv_lwc1_icol', 'CORCON_nv_lwc_icol'),
            ('CORCON_nv_lwc1_vref', 'CORCON_nv_lwc_vref'),
            ('CORCON_nv_lwc1_iref', 'CORCON_nv_lwc_iref'),
            ('CORCON_nv_lwc2_vcol', 'CORCON_nv_twc_vref'),
            ('CORCON_nv_lwc2_icol', 'CORCON_nv_twc_iref'),
            ('CORCON_nv_lwc2_vref', 'CORCON_nv_lwc_vref'),
            ('CORCON_nv_lwc2_iref', 'CORCON_nv_lwc_iref'),
            ('CORCON_nv_twc_vref',  'CORCON_nv_lwc_vref'),
            ('CORCON_nv_twc_iref',  'CORCON_nv_lwc_iref'),
            ('CLWC1ICOL', 'CLWCICOL'),
            ('CLWC1VCOL', 'CLWCVCOL'),
            ('CLWC1IREF', 'CLWCIREF'),
            ('CLWC1VREF', 'CLWCVREF'),
            ('CLWC2ICOL', 'CTWCIREF'),
            ('CLWC2VCOL', 'CTWCVREF'),
            ('CLWC2IREF', 'CLWCIREF'),
            ('CLWC2VREF', 'CLWCVREF'),
            ('CTWCICOL',  'CTWCICOL'),
            ('CTWCVCOL',  'CTWCVCOL'),
            ('CTWCIREF',  'CLWCIREF'),
            ('CTWCVREF',  'CLWCVREF')
        )

        for var in var_map:
            try:
                self.d[var[0]] = self.d[var[1]]
            except KeyError:
                self.dataset.constants[var[0]] = self.dataset[var[1]]

    def process(self):
        """
        Main processing routine.
        """

        # Get all required variables at the Nevz. sampling frequency.
        self.get_dataframe(index=self.dataset['CORCON_nv_twc_vcol'].index,
                           method='onto', limit=63)

        # Create Nevz flag, currently only based on weight on wheels
        self.d['flag'] = 0
        self.d.loc[self.d['WOW_IND'] == 1, 'flag'] = 3

        # Remap variable names iff we're running a new vane type
        self._remap_1t2l1r()

        _vanetype = self.dataset['VANETYPE'].lower()

        # Measurements are collector current, collector voltage, reference
        # current, reference voltage
        measurements = ('icol', 'vcol', 'iref', 'vref')

        # Energy required to melt/evaporate consensed water
        nvl = self.dataset['CALNVL']

        for ins in self.instruments[_vanetype]:

            # Sensor area and cp / rp ratio in constants file
            _calconst = 'CALNV{ins}'.format(ins=ins.upper())
            area = self.dataset[_calconst][1]
            K = self.dataset[_calconst][0]

            for meas in measurements:
                # Get the raw sensor reading from DECADES
                _var = 'CORCON_nv_{ins}_{meas}'.format(ins=ins, meas=meas)
                raw = self.d[_var]

                # Calibrate raw DECADES reading to Amps / Volts
                _calconst = 'C{ins}{meas}'.format(ins=ins.upper(),
                                                  meas=meas.upper())
                _cals = self.dataset[_calconst]

                _outvar = 'NV_{ins}_{meas}'.format(ins=ins.upper(),
                                                   meas=meas.upper())

                self.d[_outvar] = (_cals[0] + _cals[1] * raw) * _cals[2]

            # Calibrated collector and reference variables for the current
            # sensor
            _col_i_name = 'NV_{ins}_ICOL'.format(ins=ins.upper())
            _col_v_name = 'NV_{ins}_VCOL'.format(ins=ins.upper())
            _ref_i_name = 'NV_{ins}_IREF'.format(ins=ins.upper())
            _ref_v_name = 'NV_{ins}_VREF'.format(ins=ins.upper())

            # Power (W) = I * V
            col_p = self.d[_col_i_name] * self.d[_col_v_name]
            ref_p = self.d[_ref_i_name] * self.d[_ref_v_name]

            if ins is 'twc':
                # Cloud mask is based on variance of power from the total water
                # sensor.
                clear_air = get_no_cloud_mask(col_p, self.d.WOW_IND)

            try:
                fitted_K, params = get_fitted_k(
                    col_p, ref_p, self.d.IAS_RVSM, self.d.PS_RVSM, clear_air, K
                )

                fit_success = True
            except (RuntimeError, ValueError):
                # If the fit has failed, we only want to write
                # uncorrected variables
                fitted_K = 0
                fit_success = False

            # Create and write output variables
            w_c = DecadesVariable(
                (col_p - fitted_K * ref_p) / (self.d.TAS_RVSM * area * nvl),
                name='NV_{ins}_C'.format(ins=ins.upper())
            )
            if not fit_success:
                w_c.write = False

            w_u = DecadesVariable(
                (col_p - K * ref_p) / (self.d.TAS_RVSM * area * nvl),
                name='NV_{ins}_U'.format(ins=ins.upper())
            )

            col_power = DecadesVariable(
                col_p, name='NV_{ins}_COL_P'.format(ins=ins.upper())
            )

            ref_power = DecadesVariable(
                ref_p, name='NV_{ins}_REF_P'.format(ins=ins.upper())
            )

            for _var in (w_c, w_u, col_power):
                _var.add_flag(self.d['flag'])
                self.add_output(_var)

            if _vanetype == '1t1l2r':
                _var = ref_power
                _var.add_flag(self.d['flag'])
                self.add_output(_var)
            elif ins is 'twc':
                _var = DecadesVariable(
                   ref_p, name='NV_REF_P'
                )
                _var.add_flag(self.d['flag'])
                self.add_output(_var)