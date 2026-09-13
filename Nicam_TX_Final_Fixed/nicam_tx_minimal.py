#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: NICAM 728 TX - MINIMAAL + IQ-invert-knop
# Description: Minimale NICAM 728 TX: alleen wat strikt nodig is om de fysieke decoder te laten locken. Geen GUI-extras, config-manager, preset-knoppen of freq-sliders - dat is allemaal weggelaten om te testen of die iets met de instabiliteit te maken hebben.
# GNU Radio version: 3.10.12.0

from PyQt5 import Qt
from gnuradio import qtgui
from gnuradio import eng_notation
from gnuradio import filter
from gnuradio.filter import firdes
from gnuradio import gr
from gnuradio.fft import window
import sys
import signal
from PyQt5 import Qt
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import iio
import nicam_tx_minimal_epy_block_iq_invert as epy_block_iq_invert  # embedded python block
import nicam_tx_minimal_epy_block_nicam_final as epy_block_nicam_final  # embedded python block
import sip
import threading
import time



class nicam_tx_minimal(gr.top_block, Qt.QWidget):

    def __init__(self):
        gr.top_block.__init__(self, "NICAM 728 TX - MINIMAAL + IQ-invert-knop", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("NICAM 728 TX - MINIMAAL + IQ-invert-knop")
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

        self.settings = Qt.QSettings("gnuradio/flowgraphs", "nicam_tx_minimal")

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
        self.iq_state_probe = iq_state_probe = 0
        self.tx_freq = tx_freq = 478000000
        self.sps = sps = 2
        self.samp_rate = samp_rate = 728000
        self.rrc_gain = rrc_gain = 0.5
        self.rrc_alpha = rrc_alpha = 1.0
        self.freq_trim = freq_trim = 0
        self.freq_label = freq_label = iq_state_probe

        ##################################################
        # Blocks
        ##################################################

        self.epy_block_iq_invert = epy_block_iq_invert.blk()
        self.variable_qtgui_msg_push_button_0_0 = _variable_qtgui_msg_push_button_0_0_toggle_button = qtgui.MsgPushButton("Invert I/Q (mixer boven-/ondermenging)", 'pressed',1,"default","default")
        self.variable_qtgui_msg_push_button_0_0 = _variable_qtgui_msg_push_button_0_0_toggle_button

        self.top_layout.addWidget(_variable_qtgui_msg_push_button_0_0_toggle_button)
        self.root_raised_cosine_filter_0 = filter.interp_fir_filter_ccf(
            sps,
            firdes.root_raised_cosine(
                rrc_gain,
                samp_rate,
                (samp_rate/sps),
                rrc_alpha,
                50))
        self.qtgui_const_sink_x_0 = qtgui.const_sink_c(
            1024, #size
            "CONSTELLATION DQPSK", #name
            1, #number of inputs
            None # parent
        )
        self.qtgui_const_sink_x_0.set_update_time(0.10)
        self.qtgui_const_sink_x_0.set_y_axis((-2), 2)
        self.qtgui_const_sink_x_0.set_x_axis((-2), 2)
        self.qtgui_const_sink_x_0.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, "")
        self.qtgui_const_sink_x_0.enable_autoscale(False)
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
        self.top_layout.addWidget(self._qtgui_const_sink_x_0_win)
        def _iq_state_probe_probe():
          self.flowgraph_started.wait()
          while True:

            val = self.epy_block_iq_invert.get_inverted()
            try:
              try:
                self.doc.add_next_tick_callback(functools.partial(self.set_iq_state_probe,val))
              except AttributeError:
                self.set_iq_state_probe(val)
            except AttributeError:
              pass
            time.sleep(1.0 / (10))
        _iq_state_probe_thread = threading.Thread(target=_iq_state_probe_probe)
        _iq_state_probe_thread.daemon = True
        _iq_state_probe_thread.start()
        self.iio_pluto_sink_0 = iio.fmcomms2_sink_fc32('192.168.1.61' if '192.168.1.61' else iio.get_pluto_uri(), [True, True], 10000, False)
        self.iio_pluto_sink_0.set_len_tag_key('')
        self.iio_pluto_sink_0.set_bandwidth(1200000)
        self.iio_pluto_sink_0.set_frequency((tx_freq+freq_trim))
        self.iio_pluto_sink_0.set_samplerate(samp_rate)
        self.iio_pluto_sink_0.set_attenuation(0, 8)
        self.iio_pluto_sink_0.set_filter_params('Auto', '', 0, 0)
        self._freq_label_tool_bar = Qt.QToolBar(self)

        if lambda x: f'<span style="font-size:24pt; font-weight:bold; color:#0a7a0a;">{x:,} Hz</span>':
            self._freq_label_formatter = lambda x: f'<span style="font-size:24pt; font-weight:bold; color:#0a7a0a;">{x:,} Hz</span>'
        else:
            self._freq_label_formatter = lambda x: str(x)

        self._freq_label_tool_bar.addWidget(Qt.QLabel("IQ "))
        self._freq_label_label = Qt.QLabel(str(self._freq_label_formatter(self.freq_label)))
        self._freq_label_tool_bar.addWidget(self._freq_label_label)
        self.top_grid_layout.addWidget(self._freq_label_tool_bar, 3, 1, 1, 1)
        for r in range(3, 4):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(1, 2):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.epy_block_nicam_final = epy_block_nicam_final.blk(device_name="Voicemeeter Out B3 (VB-Audio Voicemeeter VAIO), Windows WASAPI", c1c2c3_mode=0, reserve_switch_flag=1, max_latency_ms=2000, native_samplerate=48000, preemphasis=True, lowpass_cutoff_hz=12000)


        ##################################################
        # Connections
        ##################################################
        self.msg_connect((self.variable_qtgui_msg_push_button_0_0, 'pressed'), (self.epy_block_iq_invert, 'toggle'))
        self.connect((self.epy_block_iq_invert, 0), (self.iio_pluto_sink_0, 0))
        self.connect((self.epy_block_iq_invert, 0), (self.qtgui_const_sink_x_0, 0))
        self.connect((self.epy_block_nicam_final, 0), (self.root_raised_cosine_filter_0, 0))
        self.connect((self.root_raised_cosine_filter_0, 0), (self.epy_block_iq_invert, 0))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("gnuradio/flowgraphs", "nicam_tx_minimal")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_iq_state_probe(self):
        return self.iq_state_probe

    def set_iq_state_probe(self, iq_state_probe):
        self.iq_state_probe = iq_state_probe
        self.set_freq_label(self.iq_state_probe)

    def get_tx_freq(self):
        return self.tx_freq

    def set_tx_freq(self, tx_freq):
        self.tx_freq = tx_freq
        self.iio_pluto_sink_0.set_frequency((self.tx_freq+self.freq_trim))

    def get_sps(self):
        return self.sps

    def set_sps(self, sps):
        self.sps = sps
        self.root_raised_cosine_filter_0.set_taps(firdes.root_raised_cosine(self.rrc_gain, self.samp_rate, (self.samp_rate/self.sps), self.rrc_alpha, 50))

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.iio_pluto_sink_0.set_samplerate(self.samp_rate)
        self.root_raised_cosine_filter_0.set_taps(firdes.root_raised_cosine(self.rrc_gain, self.samp_rate, (self.samp_rate/self.sps), self.rrc_alpha, 50))

    def get_rrc_gain(self):
        return self.rrc_gain

    def set_rrc_gain(self, rrc_gain):
        self.rrc_gain = rrc_gain
        self.root_raised_cosine_filter_0.set_taps(firdes.root_raised_cosine(self.rrc_gain, self.samp_rate, (self.samp_rate/self.sps), self.rrc_alpha, 50))

    def get_rrc_alpha(self):
        return self.rrc_alpha

    def set_rrc_alpha(self, rrc_alpha):
        self.rrc_alpha = rrc_alpha
        self.root_raised_cosine_filter_0.set_taps(firdes.root_raised_cosine(self.rrc_gain, self.samp_rate, (self.samp_rate/self.sps), self.rrc_alpha, 50))

    def get_freq_trim(self):
        return self.freq_trim

    def set_freq_trim(self, freq_trim):
        self.freq_trim = freq_trim
        self.iio_pluto_sink_0.set_frequency((self.tx_freq+self.freq_trim))

    def get_freq_label(self):
        return self.freq_label

    def set_freq_label(self, freq_label):
        self.freq_label = freq_label
        Qt.QMetaObject.invokeMethod(self._freq_label_label, "setText", Qt.Q_ARG("QString", str(self._freq_label_formatter(self.freq_label))))




def main(top_block_cls=nicam_tx_minimal, options=None):

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
