"""
NICAM 728 Encoder - GNU Radio Embedded Python Block (definitieve versie).

EEN blok, met opzet - niet opgesplitst in losse GRC-blokken. Reden: elke
poging om de audio-inname als apart, met een echte GNU Radio-stream
verbonden blok te laten draaien (audio_source -> custom blok, of
Audio Input -> NICAM Framer) gaf op deze GNU Radio/Windows-combinatie
hardnekkige scheduler-problemen (periodieke carrier-dropouts of een
structureel tekort aan doorgevoerde audio). De enige aanpak die in
uitgebreide tests wél volledig stabiel bleek: alles wat met audio-hardware-
timing te maken heeft (opname, resampling, buffering) in ÉÉN self-contained
bron-blok (gr.sync_block zonder stream-ingang, eigen achtergrondthread).

Om het toch overzichtelijk en volgbaar te houden, is de code hieronder in
duidelijk genummerde, apart gedocumenteerde stappen opgedeeld - je kunt dus
gewoon per methode lezen/aanpassen wat er in elke fase van het signaal
gebeurt, ook al draait het als één GRC-blok:

  STAP 0  Audio-inname (achtergrondthread, sounddevice/PortAudio)
  STAP 1  Resampling naar 32000 Hz (de door NICAM vereiste samplerate)
  STAP 2  Band-begrenzing (12 kHz laagdoorlaat)
  STAP 3  CCITT/ITU-T J.17 pre-emphasis
  STAP 4  14-bit kwantisatie + near-instantaneous companding (10 bit + schaalfactor)
  STAP 5  Frame-opbouw (FAW, control-bits, additional data, geluidswoorden)
  STAP 6  Bit-interleaving
  STAP 7  Energy-dispersal scrambling
  STAP 8  Differentiele QPSK-modulatie

Referenties:
  - ETS 300 163 (nov. 1994), hoofdstuk 4 en par. 5.3.2 (NICAM-kernspecificatie)
  - Repeater 4/1998, "NICAM-project: digitaal stereogeluid voor TV-amateurs"
    (bitvolgorde geluidswoorden: X0 (l.s.b.) eerst, oplopend naar X9 (m.s.b.),
    dan pas het pariteitsbit P - conform Fig.4)
  - ITU-T Aanbeveling J.17 (pre-emphase-karakteristiek, geverifieerd tot
    op 0,01dB tegen de officiele insertion-loss-tabel)
"""

import math
import threading
from collections import deque

import numpy as np
from scipy.signal import resample_poly, bilinear, lfilter, butter
from gnuradio import gr

try:
    import sounddevice as sd
except ImportError:
    sd = None


class blk(gr.sync_block):

    # ------------------------------------------------------------------
    # Vaste NICAM-728-constanten (spec-tabellen, zie ETS 300 163 tabel 3
    # en par. 4.1.1/4.2)
    # ------------------------------------------------------------------
    FAW_BITS = np.array([0, 1, 0, 0, 1, 1, 1, 0], dtype=np.uint8)          # frame alignment word
    SCALE_CODE = np.array([0b111, 0b110, 0b101, 0b011, 0b100], dtype=np.uint8)  # e (0..4) -> R2R1R0
    PARITY_LUT = np.array([bin(i).count('1') % 2 for i in range(64)], dtype=np.uint8)
    STEP_LUT = np.array([0.0, -90.0, -270.0, -180.0], dtype=np.float64)    # DQPSK fasesprongen

    def __init__(self, device_name='', c1c2c3_mode=0, reserve_switch_flag=1,
                 max_latency_ms=2000, native_samplerate=48000, preemphasis=True,
                 lowpass_cutoff_hz=12000):
        gr.sync_block.__init__(
            self,
            name='NICAM 728 Encoder',
            in_sig=None,
            out_sig=[np.complex64],
        )
        self._init_audio_capture(device_name, max_latency_ms, native_samplerate)
        self._init_filters(preemphasis, lowpass_cutoff_hz)
        self._init_framer_state(c1c2c3_mode, reserve_switch_flag)
        self._init_scheduler_tuning()
        self._init_diagnostics()

    # ==================================================================
    # STAP 0/1: Audio-inname + resampling - initialisatie
    # ==================================================================
    def _init_audio_capture(self, device_name, max_latency_ms, native_samplerate):
        """Zet de jitterbuffer en audiostream-configuratie klaar. De
        stream zelf wordt pas bij de eerste work()-aanroep gestart (zie
        _ensure_audio_stream_started), niet hier - GRC maakt tijdens het
        bewerken van de flowgraph tijdelijke exemplaren van dit blok aan
        om de in/uitgangen te bepalen, en dat mag geen echte hardware
        aanraken."""
        self._device_name = device_name
        self._stream = None
        self._stream_started = False

        self._native_sr = int(native_samplerate)
        g = math.gcd(self._native_sr, 32000)
        self._resample_up = 32000 // g
        self._resample_down = self._native_sr // g

        max_samples = max(32, int(32000 * max_latency_ms / 1000))
        self._buf_a = deque(maxlen=max_samples)  # linkerkanaal, @ 32kHz, na resampling
        self._buf_b = deque(maxlen=max_samples)  # rechterkanaal
        self._audio_lock = threading.Lock()

    def _ensure_audio_stream_started(self):
        """Start de echte PortAudio-inputstream (pas bij de eerste
        work()-aanroep - zie _init_audio_capture)."""
        if self._stream_started:
            return
        self._stream_started = True
        if sd is None:
            print("[NICAM encoder] WAARSCHUWING: 'sounddevice' ontbreekt "
                  "(pip install sounddevice) - geen audio, alleen stilte.")
            return
        device = self._device_name if self._device_name else None

        # Vraag de ECHTE default-samplerate van het gekozen apparaat op i.p.v.
        # te vertrouwen op de handmatig ingevulde native_samplerate-parameter
        # (die kan afwijken per host-API, bv. WASAPI vs MME).
        actual_sr = self._native_sr
        try:
            info = sd.query_devices(device, kind='input')
            detected_sr = int(round(info['default_samplerate']))
            if detected_sr != self._native_sr:
                print(f"[NICAM encoder] Let op: opgegeven native_samplerate="
                      f"{self._native_sr} Hz komt niet overeen met de "
                      f"werkelijke default-samplerate van het apparaat "
                      f"({detected_sr} Hz). Gebruik nu {detected_sr} Hz.")
            actual_sr = detected_sr
        except Exception as e:
            print(f"[NICAM encoder] kon apparaat-samplerate niet opvragen "
                  f"({e}), val terug op native_samplerate={self._native_sr} Hz.")

        self._native_sr = actual_sr
        g = math.gcd(self._native_sr, 32000)
        self._resample_up = 32000 // g
        self._resample_down = self._native_sr // g

        try:
            self._stream = sd.InputStream(
                samplerate=self._native_sr,
                channels=2,
                dtype='float32',
                device=device,
                callback=self._on_audio_block_received,
                blocksize=0,
            )
            self._stream.start()
            print(f"[NICAM encoder] audiostream gestart @ {self._native_sr} Hz, "
                  f"resample naar 32000 Hz (up={self._resample_up}, "
                  f"down={self._resample_down}).")
        except Exception as e:
            print(f"[NICAM encoder] WAARSCHUWING: kon audiostream niet "
                  f"starten ({e}) - alleen stilte.")
            self._stream = None

    def _on_audio_block_received(self, indata, frames, time_info, status):
        """STAP 1: resampling. Draait in PortAudio's eigen achtergrond-
        thread. Zet native-samplerate audio om naar de 32000 Hz die NICAM
        vereist (met correcte anti-aliasing filtering), en schrijft het
        resultaat weg naar de jitterbuffer."""
        if self._resample_up == 1 and self._resample_down == 1:
            resampled = indata
        else:
            resampled = resample_poly(indata, self._resample_up, self._resample_down, axis=0)
        with self._audio_lock:
            self._buf_a.extend(resampled[:, 0].tolist())
            self._buf_b.extend(resampled[:, 1].tolist())

    def _take_32_samples(self, buf):
        """Haalt 32 samples (=1ms @ 32kHz, precies 1 companding-blok) uit
        de jitterbuffer. Vult aan met stilte als er niet genoeg is - de
        drager mag NOOIT wachten op audio."""
        n = len(buf)
        if n >= 32:
            return np.fromiter((buf.popleft() for _ in range(32)), dtype=np.float32, count=32), False
        out = np.zeros(32, dtype=np.float32)
        if n:
            out[:n] = [buf.popleft() for _ in range(n)]
        return out, True

    # ==================================================================
    # STAP 2/3: Band-begrenzing + J.17 pre-emphasis - initialisatie
    # ==================================================================
    def _init_filters(self, preemphasis, lowpass_cutoff_hz):
        self._preemphasis_enabled = bool(preemphasis)

        # STAP 2: band-begrenzing (Butterworth laagdoorlaat). Voorkomt dat
        # STAP 3 (pre-emphasis) near-Nyquist resampling-restjes/ruis gaat
        # versterken - zonder dit klinkt pre-emphasis hard/aliasing-achtig.
        self._lp_b, self._lp_a = butter(4, lowpass_cutoff_hz / (32000 / 2), btype='low')
        self._lp_state_a = np.zeros(max(len(self._lp_b), len(self._lp_a)) - 1)
        self._lp_state_b = np.zeros(max(len(self._lp_b), len(self._lp_a)) - 1)

        # STAP 3: CCITT/ITU-T J.17 pre-emphasis. Eerste-orde shelf-filter,
        # geschaald zodat de boost bij 800Hz op 6,5dB uitkomt (de waarde die
        # specifiek voor NICAM/sound-programme is voorgeschreven).
        # H(f) = 1,103 * (1 + jf/477,15) / (1 + jf/4132,27)
        f_zero, f_pole, gain0 = 477.15, 4132.27, 1.1030
        w_z, w_p = 2 * np.pi * f_zero, 2 * np.pi * f_pole
        self._preemph_b, self._preemph_a = bilinear([gain0 / w_z, gain0], [1.0 / w_p, 1.0], 32000)
        self._preemph_state_a = np.zeros(max(len(self._preemph_b), len(self._preemph_a)) - 1)
        self._preemph_state_b = np.zeros(max(len(self._preemph_b), len(self._preemph_a)) - 1)

    def _apply_filters(self, a_samples, b_samples):
        """Past STAP 2 (band-begrenzing) en STAP 3 (pre-emphasis) toe,
        in die volgorde, als continue (stateful) filters over de hele
        aanroep heen - dus geen resets/kliks per 32-samples-blokje."""
        if not self._preemphasis_enabled:
            return a_samples, b_samples

        a, self._lp_state_a = lfilter(self._lp_b, self._lp_a, a_samples, zi=self._lp_state_a)
        b, self._lp_state_b = lfilter(self._lp_b, self._lp_a, b_samples, zi=self._lp_state_b)

        a, self._preemph_state_a = lfilter(self._preemph_b, self._preemph_a, a, zi=self._preemph_state_a)
        b, self._preemph_state_b = lfilter(self._preemph_b, self._preemph_a, b, zi=self._preemph_state_b)

        return a.astype(np.float32), b.astype(np.float32)

    # ==================================================================
    # STAP 4: 14-bit kwantisatie + near-instantaneous companding
    # ==================================================================
    @staticmethod
    def _quantize_14bit(float_samples):
        """Zet audiofloat (-1.0 .. +1.0) om naar 14-bit two's-complement
        int (-8192 .. 8191), zoals de NICAM-AD-omzetter dat zou doen."""
        return np.clip(np.round(float_samples * 8191.0), -8192, 8191).astype(np.int32)

    @staticmethod
    def _redundant_sign_bits(samples14):
        """Telt, per sample, hoeveel van de 4 bits direct onder het teken-
        bit gelijk zijn aan het tekenbit (0..4) - bepaalt hoeveel
        compressie ('coding range', ETS 300 163 tabel 3 / fig.3) mogelijk
        is zonder informatie te verliezen."""
        s = samples14.astype(np.int32) & 0x3FFF
        sign = (s >> 13) & 1
        b12 = ((s >> 12) & 1) == sign
        b11 = ((s >> 11) & 1) == sign
        b10 = ((s >> 10) & 1) == sign
        b9 = ((s >> 9) & 1) == sign
        return b12.astype(np.int32) + (b12 & b11) + (b12 & b11 & b10) + (b12 & b11 & b10 & b9)

    def _compand_block(self, samples14):
        """Comprimeert 32 samples van 14 naar 10 bit. Retourneert de 32
        gecomprimeerde waarden en de gekozen schaalfactor-exponent e (0..4,
        0=luidst/geen compressie, 4=zachtst/maximale compressie)."""
        s = samples14.astype(np.int32) & 0x3FFF
        e = int(self._redundant_sign_bits(samples14).min())  # geldt voor het HELE blok
        sign = (s >> 13) & 1
        mag9 = (s >> (4 - e)) & 0x1FF
        compressed = (sign << 9) | mag9
        return compressed.astype(np.uint16), e

    # ==================================================================
    # STAP 5: Frame-opbouw (geluidswoorden + FAW/CI/AD)
    # ==================================================================
    def _build_sound_payload(self, comp_a, e_a, comp_b, e_b):
        """Bouwt het 704-bit geluidsgedeelte van het frame: 64 geinter-
        leaved geluidswoorden van 11 bits (odd=A, even=B), inclusief
        signalling-in-parity van de schaalfactoren (ETS 300 163 par.
        4.2.4/4.2.5.5). Bitvolgorde per woord: X0 (l.s.b.) eerst, oplopend
        naar X9 (m.s.b.), dan pas de pariteitsbit P (Repeater 4/1998 fig.4)."""
        rA, rB = int(self.SCALE_CODE[e_a]), int(self.SCALE_CODE[e_b])
        R2A, R1A, R0A = (rA >> 2) & 1, (rA >> 1) & 1, rA & 1
        R2B, R1B, R0B = (rB >> 2) & 1, (rB >> 1) & 1, rB & 1

        # welke van de 64 pariteitsbits gemoduleerd worden met welke
        # schaalfactor-bit (9 woorden per bit, voor meerderheids-decodering
        # aan ontvangstzijde)
        flip = np.zeros(64, dtype=np.uint8)
        flip[0:49:6] = R2A
        flip[1:50:6] = R2B
        flip[2:51:6] = R1A
        flip[3:52:6] = R1B
        flip[4:53:6] = R0A
        flip[5:54:6] = R0B

        interleaved10 = np.zeros(64, dtype=np.uint16)
        interleaved10[0::2] = comp_a   # oneven woordnummers = A-kanaal
        interleaved10[1::2] = comp_b   # even woordnummers = B-kanaal

        top6 = (interleaved10 >> 4) & 0x3F
        parity = self.PARITY_LUT[top6] ^ flip

        shifts = np.arange(0, 10)  # X0 (l.s.b.) eerst -> X9 (m.s.b.)
        mag_bits = (interleaved10[:, None] >> shifts[None, :]) & 1
        words = np.concatenate([mag_bits, parity[:, None]], axis=1)
        return words.reshape(-1).astype(np.uint8)  # 64 * 11 = 704 bits

    def _init_framer_state(self, c1c2c3_mode, reserve_switch_flag):
        modes = {0: (0, 0, 0), 1: (0, 1, 0), 2: (1, 0, 0)}  # stereo / dual-mono / mono+data
        self._c1c2c3 = modes.get(int(c1c2c3_mode), (0, 0, 0))
        self._c4 = 1 if reserve_switch_flag else 0
        self._frame_no = 0  # 0..15, voor de frame-flag-bit C0 (16-frame-sequentie)
        self._phase = 0.0   # lopende draaggolffase (graden), continu over frames heen

        self._interleave_idx = np.array(
            [(n % 16) * 44 + (n // 16) for n in range(704)]
        )
        self._scramble_seq = self._make_scramble_sequence()  # zie STAP 7

    def _build_frame(self, comp_a, e_a, comp_b, e_b):
        """Bouwt het complete 728-bit frame: FAW (8) + control-bits (5) +
        additional data (11) + geinterleaved+gescrambled geluidsblok (704)."""
        c0 = 1 if self._frame_no < 8 else 0  # frame-flag-bit: 8x '1', dan 8x '0'
        c1, c2, c3 = self._c1c2c3
        control_bits = np.array([c0, c1, c2, c3, self._c4], dtype=np.uint8)
        additional_data = np.zeros(11, dtype=np.uint8)  # gereserveerd, niet gebruikt

        payload = self._build_sound_payload(comp_a, e_a, comp_b, e_b)
        payload_interleaved = self._interleave(payload)                     # STAP 6
        scrambled = self._scramble(control_bits, additional_data, payload_interleaved)  # STAP 7

        self._frame_no = (self._frame_no + 1) % 16
        return np.concatenate([self.FAW_BITS, scrambled])  # 8 + 720 = 728 bits

    # ==================================================================
    # STAP 6: Bit-interleaving
    # ==================================================================
    def _interleave(self, payload_704bits):
        """Herschikt de 704 geluidsbits: geschreven in verticale kolommen
        van 44 bits, uitgelezen in horizontale rijen van 16 bits (ETS 300
        163 par. 4.1.2 / Repeater 4/1998 fig.5). Verspreidt burst-fouten
        over meerdere geluidswoorden."""
        return payload_704bits[self._interleave_idx]

    # ==================================================================
    # STAP 7: Energy-dispersal scrambling
    # ==================================================================
    @staticmethod
    def _make_scramble_sequence():
        """9-bit LFSR, polynoom x^9+x^4+1, gereset naar alle-enen bij elke
        FAW. Omdat de reset elke keer identiek is en het altijd exact 720
        bits betreft, is de scramble-reeks elk frame identiek - vandaar
        eenmalig vooraf berekend i.p.v. elke ms opnieuw. Geverifieerd: de
        eerste 20 bits komen exact overeen met de startreeks uit de spec
        ("0000 0111 1011 1110 0010")."""
        state = [1] * 9
        bits = np.zeros(720, dtype=np.uint8)
        for i in range(720):
            fb = state[4] ^ state[8]
            state = [fb] + state[:-1]
            bits[i] = fb
        return bits

    def _scramble(self, control_bits, additional_data, payload_interleaved):
        to_scramble = np.concatenate([control_bits, additional_data, payload_interleaved])  # 720 bits
        return to_scramble ^ self._scramble_seq

    # ==================================================================
    # STAP 8: Differentiele QPSK-modulatie
    # ==================================================================
    def _modulate_dqpsk(self, frame_bits728):
        """Zet 728 bits om in 364 DQPSK-symbolen. Fasesprongen exact
        volgens de spec-tabel (par. 5.3.2): 00->0 graden, 01->-90,
        10->-270, 11->-180. De fase loopt continu door over frames heen
        (alleen de scrambler wordt per frame gereset, de draaggolffase
        niet)."""
        a = frame_bits728[0::2]
        b = frame_bits728[1::2]
        idx = a.astype(np.int64) * 2 + b.astype(np.int64)
        steps = self.STEP_LUT[idx]
        phases = (np.cumsum(steps) + self._phase) % 360.0
        self._phase = float(phases[-1])
        rad = np.deg2rad(phases)
        return (np.cos(rad) + 1j * np.sin(rad)).astype(np.complex64)

    # ==================================================================
    # Scheduler-afstemming (lessen uit eerder debuggen op deze GNU Radio/
    # Windows-combinatie: zonder deze twee regels ontstaan hardnekkige
    # periodieke carrier-dropouts).
    # ==================================================================
    def _init_scheduler_tuning(self):
        self.set_output_multiple(364)
        self.set_max_noutput_items(364 * 50)  # max. 50 frames (~50ms) per work()-aanroep

    def _init_diagnostics(self):
        self._underrun_frames = 0
        self._total_frames = 0
        self._last_report = 0

    def _maybe_report_underrun(self):
        if self._total_frames - self._last_report >= 5000:
            self._last_report = self._total_frames
            pct = 100.0 * self._underrun_frames / max(1, self._total_frames)
            print(f"[NICAM encoder] stilte-invulling: {pct:.2f}% "
                  f"({self._underrun_frames}/{self._total_frames} frames)")

    # ==================================================================
    # GNU Radio scheduler-interface
    # ==================================================================
    def work(self, input_items, output_items):
        self._ensure_audio_stream_started()
        out = output_items[0]
        n_frames = len(out) // 364

        # Lock zo KORT mogelijk vasthouden - alleen om ruwe samples uit de
        # jitterbuffer te halen. PortAudio's eigen callback-thread heeft
        # een real-time deadline; als wij de lock te lang vasthouden
        # tijdens het (tragere) rekenwerk, kan audio verloren gaan.
        raw_blocks = []
        with self._audio_lock:
            for _ in range(n_frames):
                a_f, under_a = self._take_32_samples(self._buf_a)
                b_f, under_b = self._take_32_samples(self._buf_b)
                if under_a or under_b:
                    self._underrun_frames += 1
                raw_blocks.append((a_f, b_f))

        # De filters (STAP 2+3) worden op de HELE aanroep tegelijk toegepast
        # (aaneengeregen), niet per 32-samples-blokje apart - scipy's
        # lfilter() heeft namelijk best wat overhead per aanroep, en dat
        # 50x per work()-aanroep doen i.p.v. 1x is ~20x trager. Dat kostte
        # eerder precies genoeg extra tijd om de audiothread's real-time
        # deadline te missen (hoorbaar als geknetter/gekraak/wegvallen).
        if raw_blocks and self._preemphasis_enabled:
            a_all = np.concatenate([a for a, _ in raw_blocks])
            b_all = np.concatenate([b for _, b in raw_blocks])
            a_all, b_all = self._apply_filters(a_all, b_all)
            raw_blocks = [
                (a_all[i * 32:(i + 1) * 32], b_all[i * 32:(i + 1) * 32])
                for i in range(len(raw_blocks))
            ]

        produced = 0
        for a_f, b_f in raw_blocks:
            a14 = self._quantize_14bit(a_f)                                # STAP 4
            b14 = self._quantize_14bit(b_f)
            comp_a, e_a = self._compand_block(a14)
            comp_b, e_b = self._compand_block(b14)

            frame_bits = self._build_frame(comp_a, e_a, comp_b, e_b)       # STAP 5,6,7
            out[produced:produced + 364] = self._modulate_dqpsk(frame_bits)  # STAP 8
            produced += 364
            self._total_frames += 1

        self._maybe_report_underrun()
        return produced

    def stop(self):
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
        return True
