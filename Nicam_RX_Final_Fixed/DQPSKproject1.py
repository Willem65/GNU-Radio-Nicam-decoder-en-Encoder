#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: RX NICAM Receiver
# GNU Radio version: 3.10.12.0

from PyQt5 import Qt
from gnuradio import qtgui
from PyQt5 import QtCore
from gnuradio import blocks
from gnuradio import digital
from gnuradio import filter
from gnuradio.filter import firdes
from gnuradio import gr
from gnuradio.fft import window
import sys
import signal
from PyQt5 import Qt
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
from gnuradio import iio
import DQPSKproject1_epy_block_0_1_0 as epy_block_0_1_0  # embedded python block
import DQPSKproject1_epy_block_iq_invert as epy_block_iq_invert  # embedded python block
import sip
import threading



class DQPSKproject1(gr.top_block, Qt.QWidget):

    def __init__(self):
        gr.top_block.__init__(self, "RX NICAM Receiver", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("RX NICAM Receiver")
        qtgui.util.check_set_qss()
        try:
            self.setWindowIcon(Qt.QIcon.fromTheme('gnuradio-grc'))
        except BaseException as exc:
            print(f"Qt GUI: Could not set Icon: {str(exc)}", file=sys.stderr)
        self.top_scroll_layout = Qt.QVBoxLayout()
        self.setLayout(self.top_scroll_layout)
        self.top_scroll = Qt.QScrollArea()
        self.top_scroll.setFrameStyle(Qt.QFrame.NoFrame)
        self.top_scroll_layout.addWidget(self.top_scroll)
        self.top_scroll.setWidgetResizable(True)
        self.top_widget = Qt.QWidget()
        self.top_scroll.setWidget(self.top_widget)
        self.top_layout = Qt.QVBoxLayout(self.top_widget)
        self.top_grid_layout = Qt.QGridLayout()
        self.top_layout.addLayout(self.top_grid_layout)

        self.settings = Qt.QSettings("gnuradio/flowgraphs", "DQPSKproject1")

        try:
            geometry = self.settings.value("geometry")
            if geometry:
                self.restoreGeometry(geometry)
        except BaseException as exc:
            print(f"Qt GUI: Could not restore geometry: {str(exc)}", file=sys.stderr)
        self.flowgraph_started = threading.Event()

        ##################################################
        # Variables
        ##################################################
        self.sps = sps = 2
        self.samp_rate = samp_rate = 728000
        self.rrc_gain = rrc_gain = 1
        self.rrc_alpha = rrc_alpha = 1.0
        self.qpsk_const_0 = qpsk_const_0 = digital.constellation_qpsk().base()
        self.qpsk_const_0.set_npwr(1.0)
        self.qpsk_const = qpsk_const = digital.constellation_qpsk().base()
        self.qpsk_const.set_npwr(1.0)
        self.freq_tune = freq_tune = 477999500
        self.buffer_size = buffer_size = 0
        self.Fil_Gain = Fil_Gain = 1.3
        self.BW_tune = BW_tune = 1.5

        ##################################################
        # Blocks
        ##################################################

        self._freq_tune_range = qtgui.Range(477000000, 479700000, 100, 477999500, 20)
        self._freq_tune_win = qtgui.RangeWidget(self._freq_tune_range, self.set_freq_tune, "Frequentie", "counter_slider", int, QtCore.Qt.Horizontal)
        self.top_layout.addWidget(self._freq_tune_win)
        self._Fil_Gain_range = qtgui.Range(0.5, 2.0, 0.04, 1.3, 20)
        self._Fil_Gain_win = qtgui.RangeWidget(self._Fil_Gain_range, self.set_Fil_Gain, "Filter Gain", "slider", float, QtCore.Qt.Horizontal)
        self.top_layout.addWidget(self._Fil_Gain_win)
        self._BW_tune_range = qtgui.Range(0.1, 2.0, 0.01, 1.5, 20)
        self._BW_tune_win = qtgui.RangeWidget(self._BW_tune_range, self.set_BW_tune, "BW", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_layout.addWidget(self._BW_tune_win)
        self.variable_qtgui_msg_push_button_0_0 = _variable_qtgui_msg_push_button_0_0_toggle_button = qtgui.MsgPushButton("Invert I/Q (mixer boven-/ondermenging)", 'pressed',1,"default","default")
        self.variable_qtgui_msg_push_button_0_0 = _variable_qtgui_msg_push_button_0_0_toggle_button

        self.top_layout.addWidget(_variable_qtgui_msg_push_button_0_0_toggle_button)
        self.root_raised_cosine_filter_0_0 = filter.fir_filter_ccf(
            1,
            firdes.root_raised_cosine(
                Fil_Gain,
                (samp_rate*4),
                ((samp_rate*4)/sps),
                BW_tune,
                50))
        self.qtgui_freq_sink_x_0_0 = qtgui.freq_sink_c(
            2048, #size
            window.WIN_BLACKMAN_hARRIS, #wintype
            10000000, #fc
            20000000, #bw
            "RX", #name
            1,
            None # parent
        )
        self.qtgui_freq_sink_x_0_0.set_update_time(0.10)
        self.qtgui_freq_sink_x_0_0.set_y_axis((-160), 10)
        self.qtgui_freq_sink_x_0_0.set_y_label('Relative Gain', 'dB')
        self.qtgui_freq_sink_x_0_0.set_trigger_mode(qtgui.TRIG_MODE_FREE, 0.0, 0, "")
        self.qtgui_freq_sink_x_0_0.enable_autoscale(False)
        self.qtgui_freq_sink_x_0_0.enable_grid(False)
        self.qtgui_freq_sink_x_0_0.set_fft_average(1.0)
        self.qtgui_freq_sink_x_0_0.enable_axis_labels(True)
        self.qtgui_freq_sink_x_0_0.enable_control_panel(True)
        self.qtgui_freq_sink_x_0_0.set_fft_window_normalized(False)



        labels = ['', '', '', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["blue", "red", "green", "black", "cyan",
            "magenta", "yellow", "dark red", "dark green", "dark blue"]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.qtgui_freq_sink_x_0_0.set_line_label(i, "Data {0}".format(i))
            else:
                self.qtgui_freq_sink_x_0_0.set_line_label(i, labels[i])
            self.qtgui_freq_sink_x_0_0.set_line_width(i, widths[i])
            self.qtgui_freq_sink_x_0_0.set_line_color(i, colors[i])
            self.qtgui_freq_sink_x_0_0.set_line_alpha(i, alphas[i])

        self._qtgui_freq_sink_x_0_0_win = sip.wrapinstance(self.qtgui_freq_sink_x_0_0.qwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._qtgui_freq_sink_x_0_0_win, 1, 1, 1, 1)
        for r in range(1, 2):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(1, 2):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.qtgui_const_sink_x_0 = qtgui.const_sink_c(
            1024, #size
            'qpsk_const', #name
            1, #number of inputs
            None # parent
        )
        self.qtgui_const_sink_x_0.set_update_time(0.10)
        self.qtgui_const_sink_x_0.set_y_axis((-2), 2)
        self.qtgui_const_sink_x_0.set_x_axis((-2), 2)
        self.qtgui_const_sink_x_0.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, "")
        self.qtgui_const_sink_x_0.enable_autoscale(True)
        self.qtgui_const_sink_x_0.enable_grid(False)
        self.qtgui_const_sink_x_0.enable_axis_labels(True)


        labels = ['', '', '', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["blue", "red", "green", "black", "cyan",
            "magenta", "yellow", "dark red", "dark green", "dark blue"]
        styles = [0, 0, 0, 0, 0,
            0, 0, 0, 0, 0]
        markers = [0, 0, 0, 0, 0,
            0, 0, 0, 0, 0]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.qtgui_const_sink_x_0.set_line_label(i, "Data {0}".format(i))
            else:
                self.qtgui_const_sink_x_0.set_line_label(i, labels[i])
            self.qtgui_const_sink_x_0.set_line_width(i, widths[i])
            self.qtgui_const_sink_x_0.set_line_color(i, colors[i])
            self.qtgui_const_sink_x_0.set_line_style(i, styles[i])
            self.qtgui_const_sink_x_0.set_line_marker(i, markers[i])
            self.qtgui_const_sink_x_0.set_line_alpha(i, alphas[i])

        self._qtgui_const_sink_x_0_win = sip.wrapinstance(self.qtgui_const_sink_x_0.qwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._qtgui_const_sink_x_0_win, 1, 0, 1, 1)
        for r in range(1, 2):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 1):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.iio_pluto_source_0 = iio.fmcomms2_source_fc32('192.168.1.62' if '192.168.1.62' else iio.get_pluto_uri(), [True, True], 14000)
        self.iio_pluto_source_0.set_len_tag_key('')
        self.iio_pluto_source_0.set_frequency(freq_tune)
        self.iio_pluto_source_0.set_samplerate(samp_rate)
        self.iio_pluto_source_0.set_gain_mode(0, 'slow_attack')
        self.iio_pluto_source_0.set_gain(0, 73)
        self.iio_pluto_source_0.set_quadrature(True)
        self.iio_pluto_source_0.set_rfdc(True)
        self.iio_pluto_source_0.set_bbdc(True)
        self.iio_pluto_source_0.set_filter_params('Auto', '', 0, 0)
        self.epy_block_iq_invert = epy_block_iq_invert.blk()
        self.epy_block_0_1_0 = epy_block_0_1_0.blk(device_name=100, native_samplerate=48000, apply_deemphasis=True, lock_confirm_frames=3, lock_loss_frames=4, output_gain=1, max_latency_ms=2000)
        self.digital_symbol_sync_xx_0 = digital.symbol_sync_cc(
            digital.TED_GARDNER,
            sps,
            0.5,
            1.414,
            1,
            1.5,
            1,
            digital.constellation_qpsk().base(),
            digital.IR_MMSE_8TAP,
            128,
            [])
        self.digital_map_bb_0_0_0_0 = digital.map_bb([1,2,0,3])
        self.digital_map_bb_0 = digital.map_bb([0,2,3,1])
        self.digital_diff_decoder_bb_0 = digital.diff_decoder_bb(4, digital.DIFF_DIFFERENTIAL)
        self.digital_costas_loop_cc_0 = digital.costas_loop_cc(0.6, 4, False)
        self.digital_constellation_decoder_cb_0 = digital.constellation_decoder_cb(qpsk_const)
        self.blocks_unpack_k_bits_bb_0 = blocks.unpack_k_bits_bb(2)
        self.blocks_file_sink_0_0_1 = blocks.file_sink(gr.sizeof_char*1, 'C:\\temp\\voor_diff.ts', False)
        self.blocks_file_sink_0_0_1.set_unbuffered(False)
        self.blocks_file_sink_0_0_0_0 = blocks.file_sink(gr.sizeof_char*1, 'C:\\temp\\na_diff.ts', False)
        self.blocks_file_sink_0_0_0_0.set_unbuffered(False)


        ##################################################
        # Connections
        ##################################################
        self.msg_connect((self.variable_qtgui_msg_push_button_0_0, 'pressed'), (self.epy_block_iq_invert, 'toggle'))
        self.connect((self.blocks_unpack_k_bits_bb_0, 0), (self.epy_block_0_1_0, 0))
        self.connect((self.digital_constellation_decoder_cb_0, 0), (self.blocks_file_sink_0_0_1, 0))
        self.connect((self.digital_constellation_decoder_cb_0, 0), (self.digital_map_bb_0_0_0_0, 0))
        self.connect((self.digital_costas_loop_cc_0, 0), (self.digital_constellation_decoder_cb_0, 0))
        self.connect((self.digital_costas_loop_cc_0, 0), (self.qtgui_const_sink_x_0, 0))
        self.connect((self.digital_diff_decoder_bb_0, 0), (self.blocks_file_sink_0_0_0_0, 0))
        self.connect((self.digital_diff_decoder_bb_0, 0), (self.digital_map_bb_0, 0))
        self.connect((self.digital_map_bb_0, 0), (self.blocks_unpack_k_bits_bb_0, 0))
        self.connect((self.digital_map_bb_0_0_0_0, 0), (self.digital_diff_decoder_bb_0, 0))
        self.connect((self.digital_symbol_sync_xx_0, 0), (self.digital_costas_loop_cc_0, 0))
        self.connect((self.epy_block_iq_invert, 0), (self.root_raised_cosine_filter_0_0, 0))
        self.connect((self.iio_pluto_source_0, 0), (self.epy_block_iq_invert, 0))
        self.connect((self.root_raised_cosine_filter_0_0, 0), (self.digital_symbol_sync_xx_0, 0))
        self.connect((self.root_raised_cosine_filter_0_0, 0), (self.qtgui_freq_sink_x_0_0, 0))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("gnuradio/flowgraphs", "DQPSKproject1")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_sps(self):
        return self.sps

    def set_sps(self, sps):
        self.sps = sps
        self.digital_symbol_sync_xx_0.set_sps(self.sps)
        self.root_raised_cosine_filter_0_0.set_taps(firdes.root_raised_cosine(self.Fil_Gain, (self.samp_rate*4), ((self.samp_rate*4)/self.sps), self.BW_tune, 50))

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.iio_pluto_source_0.set_samplerate(self.samp_rate)
        self.root_raised_cosine_filter_0_0.set_taps(firdes.root_raised_cosine(self.Fil_Gain, (self.samp_rate*4), ((self.samp_rate*4)/self.sps), self.BW_tune, 50))

    def get_rrc_gain(self):
        return self.rrc_gain

    def set_rrc_gain(self, rrc_gain):
        self.rrc_gain = rrc_gain

    def get_rrc_alpha(self):
        return self.rrc_alpha

    def set_rrc_alpha(self, rrc_alpha):
        self.rrc_alpha = rrc_alpha

    def get_qpsk_const_0(self):
        return self.qpsk_const_0

    def set_qpsk_const_0(self, qpsk_const_0):
        self.qpsk_const_0 = qpsk_const_0

    def get_qpsk_const(self):
        return self.qpsk_const

    def set_qpsk_const(self, qpsk_const):
        self.qpsk_const = qpsk_const
        self.digital_constellation_decoder_cb_0.set_constellation(self.qpsk_const)

    def get_freq_tune(self):
        return self.freq_tune

    def set_freq_tune(self, freq_tune):
        self.freq_tune = freq_tune
        self.iio_pluto_source_0.set_frequency(self.freq_tune)

    def get_buffer_size(self):
        return self.buffer_size

    def set_buffer_size(self, buffer_size):
        self.buffer_size = buffer_size

    def get_Fil_Gain(self):
        return self.Fil_Gain

    def set_Fil_Gain(self, Fil_Gain):
        self.Fil_Gain = Fil_Gain
        self.root_raised_cosine_filter_0_0.set_taps(firdes.root_raised_cosine(self.Fil_Gain, (self.samp_rate*4), ((self.samp_rate*4)/self.sps), self.BW_tune, 50))

    def get_BW_tune(self):
        return self.BW_tune

    def set_BW_tune(self, BW_tune):
        self.BW_tune = BW_tune
        self.root_raised_cosine_filter_0_0.set_taps(firdes.root_raised_cosine(self.Fil_Gain, (self.samp_rate*4), ((self.samp_rate*4)/self.sps), self.BW_tune, 50))




def main(top_block_cls=DQPSKproject1, options=None):
    if gr.enable_realtime_scheduling() != gr.RT_OK:
        gr.logger("realtime").warn("Error: failed to enable real-time scheduling.")

    qapp = Qt.QApplication(sys.argv)

    tb = top_block_cls()

    tb.start()
    tb.flowgraph_started.set()

    tb.show()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()

        Qt.QApplication.quit()

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    timer = Qt.QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    qapp.exec_()

if __name__ == '__main__':
    main()
