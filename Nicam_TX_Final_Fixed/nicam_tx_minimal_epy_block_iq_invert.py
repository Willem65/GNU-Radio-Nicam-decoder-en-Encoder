"""
IQ Invert Toggle - GNU Radio Embedded Python Block.

Simpel doorgeefluik voor een complex64-stream, dat via een message-knop
(QT GUI Message Push Button) live omgeschakeld kan worden tussen normaal
doorgeven en het complex conjugeren van het signaal (Q wordt -Q).

Waarom dit nodig is: een externe RF-mixer kan, afhankelijk van of je
boven- of ondermenging gebruikt, het spectrum spiegelen. Voor een
QPSK/DQPSK-signaal komt dat neer op het conjugeren van het IQ-signaal (de
richting van de fase-rotatie draait om). Met deze knop kun je dat ter
plekke compenseren/testen zonder de flowgraph te herstarten.
"""

import numpy as np
from gnuradio import gr
import pmt


class blk(gr.sync_block):

    def __init__(self):
        gr.sync_block.__init__(
            self,
            name='IQ Invert Toggle',
            in_sig=[np.complex64],
            out_sig=[np.complex64],
        )
        self._inverted = False
        self.message_port_register_in(pmt.intern('toggle'))
        self.set_msg_handler(pmt.intern('toggle'), self._handle_toggle)

    def _handle_toggle(self, msg):
        self._inverted = not self._inverted
        state = "GEINVERTEERD (Q = -Q)" if self._inverted else "NORMAAL"
        print(f"[IQ Invert Toggle] nu: {state}")

    def get_inverted(self):
        return int(self._inverted)

    def work(self, input_items, output_items):
        in0 = input_items[0]
        out = output_items[0]
        if self._inverted:
            out[:] = np.conj(in0)
        else:
            out[:] = in0
        return len(out)
