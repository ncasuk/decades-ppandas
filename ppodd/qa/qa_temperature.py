import numpy as np

from .base import QAMod, QAFigure
from ppodd.utils.calcs import sp_mach


class TemperatureQA(QAMod):
    inputs = [
        'TAT_DI_R',
        'TAT_ND_R',
    ]

    def make_cloud_plot(self, fig):
        lwc_axis = fig.timeseries_axes([.1, .80, .8, .05], labelx=False)

        clear_air = self.dataset['NV_CLEAR_AIR_MASK'].data.asfreq('1S')
        cloud = 1 - clear_air

        wow = self.dataset['WOW_IND'].data.asfreq('1S')
        wow = wow.reindex(cloud.index).bfill().ffill()

        cloud.loc[wow == 1] = np.nan

        _x = np.abs(np.vstack((cloud, cloud)))

        lwc_axis.pcolormesh(cloud.index, [0, 1], _x, cmap='Blues_r')

        lwc_axis.set_ylabel('Cloud', rotation=0, labelpad=20)
        lwc_axis.set_xticks([])
        lwc_axis.set_yticks([])

    def make_heater_plot(self, fig):
        heater_axis = fig.timeseries_axes([.1, .85, .8, .02], labelx=False)
        heater = self.dataset['PRTAFT_deiced_temp_flag'].data.asfreq('1S')
        heater.loc[heater == 0] = np.nan
        _x = np.vstack([heater, heater])

        heater_axis.pcolormesh(
            heater.index,
            [0, 1],
            _x,
            cmap='RdYlBu'
        )

        heater_axis.set_xticks([])
        heater_axis.set_yticks([])
        heater_axis.set_ylabel('DI heater', rotation=0, labelpad=20)

    def make_temperature_plot(self, fig):
        temp_axis, temp2_axis = fig.timeseries_axes([.1, .55, .8, .25], twinx=True)
        temp_axis.patch.set_alpha(0.0)

        tat_di = self.dataset['TAT_DI_R'].data.asfreq('1S')
        tat_nd = self.dataset['TAT_ND_R'].data.asfreq('1S')

        temp2_axis.plot(
            tat_di - tat_nd, color='k', linewidth=.5, alpha=.3, label='DI - ND'
        )

        temp_axis.plot(tat_nd, label='ND')
        temp_axis.plot(tat_di, label='DI')

        temp2_axis.add_zero_line()
        temp_axis.set_xticklabels([])
        temp_axis.set_ylabel('Temp. (K)')
        temp2_axis.set_ylabel('$\Delta$ Temp. (K)')
        temp_axis.legend(fontsize=6)
        temp2_axis.legend(fontsize=6)

    def make_mach_alt_plot(self, fig):
        sp = self.dataset['PS_RVSM'].data.asfreq('1S')
        psp = self.dataset['Q_RVSM'].data.asfreq('1S')

        ma_axis, pa_axis = fig.timeseries_axes([.1, .37, .8, .17], twinx=True)

        ma_axis.plot(sp_mach(psp, sp), label='Mach', color='purple')
        ma_axis.legend(fontsize=6)

        pa_axis.plot(self.dataset['PALT_RVS'].data.asfreq('1S'),
                     color='green', label='Press. Alt.')
        pa_axis.legend()

        ma_axis.set_xlabel('Time (UTC)')
        ma_axis.set_ylabel('Mach #')
        pa_axis.set_ylabel('Pressure Alt (m)')

    def make_scatter_plot(self, fig):
        scat_axis = fig.axes([.1, .12, .38, .2])

        tat_di = self.dataset['TAT_DI_R'].data.asfreq('1S')
        tat_nd = self.dataset['TAT_ND_R'].data.asfreq('1S')
        wow = self.dataset['WOW_IND'].data.asfreq('1S')

        tat_di.loc[wow == 1] = np.nan
        tat_nd.loc[wow == 1] = np.nan

        scat_axis.scatter(tat_di, tat_nd, 1, c=tat_di.index)

        scat_axis.add_121()
        scat_axis.set_xlabel('TAT DI (K)')
        scat_axis.set_ylabel('TAT ND (K)')

    def make_spectra_plot(self, fig):
        def spectra():
            _index = self.dataset['TAT_DI_R'].data.index
            _mask = (_index > fig.to_time) & (_index < fig.land_time)

            tat_di = self.dataset['TAT_DI_R'].data.loc[_mask]
            tat_nd = self.dataset['TAT_ND_R'].data.loc[_mask]
            freqs = np.fft.fftfreq(tat_di.size, 1/32)

            ps_nd = np.abs(np.fft.fft(tat_nd))**2
            ps_di = np.abs(np.fft.fft(tat_di))**2
            idx = np.argsort(freqs)

            return freqs[idx], ps_nd[idx], ps_di[idx]

        def running_mean(x, N):
            return np.convolve(x, np.ones((N,))/N)[(N-1):]

        freqs, ps_nd, ps_di = spectra()

        spec_axis = fig.axes([.55, .12, .38, .2])
        spec_axis.loglog(
            freqs[freqs < 15.5],
            running_mean(ps_nd, 200)[freqs < 15.5],
            label='ND'
        )

        spec_axis.loglog(
            freqs[freqs < 15.5],
            running_mean(ps_di, 200)[freqs < 15.5],
            label='DI'
        )

        spec_axis.set_ylim(.5, 10**3)
        spec_axis.set_xlim(1, 16)

        spec_axis.set_xlabel('Frequency')
        spec_axis.set_ylabel('Power')
        spec_axis.legend(fontsize=6)

    def make_info_text(self, fig):

        GOOD_THRESH = 0.5
        GOOD_FRAC = 0.95

        _index = self.dataset['TAT_DI_R'].data.index
        _mask = (_index > fig.to_time) & (_index < fig.land_time)

        tat_di = self.dataset['TAT_DI_R'].data.loc[_mask]
        tat_nd = self.dataset['TAT_ND_R'].data.loc[_mask]

        num_good = sum(np.abs(tat_di - tat_nd) <= GOOD_THRESH)
        num_bad = sum(np.abs(tat_di - tat_nd) > GOOD_THRESH)

        good = num_good / (num_good + num_bad) >= GOOD_FRAC

        if good:
            _txt = '|$\Delta TAT$| < 0.5 K for at least 95% of flight'
            _col = 'green'
        else:
            _txt = '|$\Delta TAT$| > 0.5 K for at least 5% of flight'
            _col = 'red'

        fig.text(.5, .92, _txt, horizontalalignment='center', color=_col,
                 size='small')

        di_higher = (tat_di - tat_nd).mean() > 0
        if di_higher:
            _txt = 'On average, TAT_DI reads higher'
        else:
            _txt = 'On average, TAT_ND reads higher'
        fig.text(.5, .90, _txt, horizontalalignment='center', size='small')

        _txt = 'DI: {0} ({1}), NDI: {2} ({3})'.format(
            *(self.dataset['DITSENS'] + self.dataset['NDTSENS'])
        )

        fig.text(.5, .88, _txt, horizontalalignment='center', size='small')

    def run(self):
        with QAFigure(self.dataset, 'Temperature Probes') as fig:
            self.make_heater_plot(fig)
            self.make_cloud_plot(fig)
            self.make_temperature_plot(fig)
            self.make_mach_alt_plot(fig)
            self.make_scatter_plot(fig)
            self.make_spectra_plot(fig)
            self.make_info_text(fig)
