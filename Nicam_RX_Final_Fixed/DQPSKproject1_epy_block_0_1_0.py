"""
NICAM 728 Decoder - GNU Radio Embedded Python Block.

Het spiegelbeeld van de bestaande encoder (epy_block_nicam_final): waar de
encoder van stereo-audio naar een complex64 DQPSK-stream ging, gaat dit
blok van een RUWE BITSTROOM (na framesync-loze demodulatie) terug naar
stereo-audio, die live wordt afgespeeld via sounddevice/PortAudio.

VERWACHTE PLAATS IN JOUW FLOWGRAPH (op basis van je screenshot):

    Pluto RX -> ... -> Symbol Sync -> Costas Loop -> Constellation Decoder
             -> Differential Decoder -> Map -> Unpack K Bits -> [DIT BLOK]

"Unpack K Bits" (K=2) levert 1 losse bit per output-item (waarde 0 of 1,
als byte/uchar) - dat is precies de invoer die dit blok verwacht:
    in_sig  = [np.uint8]      (1 bit per sample, 728 kbit/s)
    out_sig = []               (geen stream-uitgang - audio gaat direct
                                 naar de geluidskaart, net zoals de encoder
                                 audio direct van de geluidskaart INNAM)

Net als bij de encoder geldt hier: alles wat met audio-hardware-timing te
maken heeft (afspelen) draait in een eigen achtergrondthread (PortAudio's
output-callback), losgekoppeld van de GNU Radio-scheduler-thread via een
jitterbuffer - exact de architectuur die we bij de encoder al hadden
uitgewerkt, nu in de andere richting.

De negen STAP-pen zijn hier het spiegelbeeld van de encoder:

  STAP D1  Framesynchronisatie (FAW zoeken/vasthouden in de bitstroom)
  STAP D2  Descramblen (dezelfde LFSR-reeks als de encoder, XOR terug)
  STAP D3  De-interleaven (inverse permutatie van de encoder-interleave)
  STAP D4  Control-bits + additional data uitlezen
  STAP D5  Schaalfactor terugwinnen (meerderheidsstem over de 9 pariteitsbits)
  STAP D6  Decompanderen (10 bit + schaalfactor -> 14-bit sample)
  STAP D7  De-emphasis (inverse J.17-filter)
  STAP D8  Resample naar de native samplerate van de geluidskaart + afspelen

Referenties: zie epy_block_nicam_final.py (ETS 300 163, Repeater 4/1998,
ITU-T J.17) - dezelfde spec, nu in omgekeerde richting toegepast.
"""

import math
import threading
from collections import deque

import numpy as np
from scipy.signal import resample_poly, bilinear, lfilter
from gnuradio import gr

try:
    import sounddevice as sd
except ImportError:
    sd = None


class blk(gr.sync_block):

    # ------------------------------------------------------------------
    # Zelfde vaste NICAM-728-constanten als de encoder (moeten identiek
    # zijn - het zijn twee kanten van dezelfde spec).
    # ------------------------------------------------------------------
    FAW_BITS = np.array([0, 1, 0, 0, 1, 1, 1, 0], dtype=np.uint8)
    SCALE_CODE = np.array([0b111, 0b110, 0b101, 0b011, 0b100], dtype=np.uint8)
    CODE_TO_E = {int(code): e for e, code in enumerate(SCALE_CODE)}
    PARITY_LUT = np.array([bin(i).count('1') % 2 for i in range(64)], dtype=np.uint8)

    # inverse van encoder's self._interleave_idx (eenmalig te berekenen,
    # zie STAP D3 hieronder)
    _ENC_INTERLEAVE_IDX = np.array([(n % 16) * 44 + (n // 16) for n in range(704)])

    def __init__(self, device_name='', native_samplerate=48000,
                 apply_deemphasis=True, lock_confirm_frames=3,
                 lock_loss_frames=4, output_gain=1.0, max_latency_ms=500):
        gr.sync_block.__init__(
            self,
            name='NICAM 728 Decoder',
            in_sig=[np.uint8],
            out_sig=[],
        )
        self._init_audio_output(device_name, native_samplerate, max_latency_ms)
        self._init_deemphasis(apply_deemphasis)
        self._init_frame_sync(lock_confirm_frames, lock_loss_frames)
        self._output_gain = float(output_gain)
        self._init_diagnostics()

    # ==================================================================
    # STAP D8 (uitvoerkant): audio-uitvoer - initialisatie
    # ==================================================================
    def _init_audio_output(self, device_name, native_samplerate, max_latency_ms):
        """Zelfde voorzichtigheidsprincipe als de encoder: de echte
        PortAudio-stream wordt pas bij de eerste work()-aanroep gestart,
        niet hier - GRC maakt tijdens het bewerken van de flowgraph
        tijdelijke exemplaren van dit blok aan."""
        self._device_name = device_name
        self._stream = None
        self._stream_started = False

        self._native_sr = int(native_samplerate)
        g = math.gcd(32000, self._native_sr)
        self._resample_up = self._native_sr // g
        self._resample_down = 32000 // g

        max_samples = max(64, int(self._native_sr * max_latency_ms / 1000))
        self._out_buf_a = deque(maxlen=max_samples)  # links, @ native_samplerate
        self._out_buf_b = deque(maxlen=max_samples)  # rechts
        self._out_lock = threading.Lock()

    def _ensure_audio_output_started(self):
        if self._stream_started:
            return
        self._stream_started = True
        if sd is None:
            print("[NICAM decoder] WAARSCHUWING: 'sounddevice' ontbreekt "
                  "(pip install sounddevice) - geen audio-uitvoer.")
            return
        device = self._device_name if self._device_name else None
        if isinstance(device, str) and device.strip().isdigit():
            # numerieke apparaat-index (bv. "100") -> als integer doorgeven,
            # zodat dubbelzinnige naamconflicten (meerdere host-API's met
            # dezelfde apparaatnaam, zoals DirectSound + WASAPI) omzeild
            # worden. sounddevice matcht een STRING altijd op naam-substring,
            # nooit op index - vandaar deze expliciete conversie.
            device = int(device.strip())

        actual_sr = self._native_sr
        self._out_channels = 2
        try:
            info = sd.query_devices(device, kind='output')
            detected_sr = int(round(info['default_samplerate']))
            if detected_sr != self._native_sr:
                print(f"[NICAM decoder] Let op: opgegeven native_samplerate="
                      f"{self._native_sr} Hz komt niet overeen met de "
                      f"werkelijke default-samplerate van het uitvoerapparaat "
                      f"({detected_sr} Hz). Gebruik nu {detected_sr} Hz.")
            actual_sr = detected_sr
            # veel virtuele apparaten (VB-Cable/Voicemeeter-stroken) bieden
            # meer dan 2 uitvoerkanalen aan (vaak 8) en weigeren een harde
            # 2-kanaals-aanvraag. Gebruik het werkelijke aantal, en zet
            # straks L/R op de eerste twee kanalen, de rest stil.
            max_ch = int(info['max_output_channels'])
            if max_ch < 2:
                print(f"[NICAM decoder] WAARSCHUWING: apparaat biedt maar "
                      f"{max_ch} uitvoerkanaal/kanalen aan (geen stereo mogelijk).")
                self._out_channels = max(1, max_ch)
            elif max_ch != 2:
                print(f"[NICAM decoder] apparaat biedt {max_ch} uitvoerkanalen "
                      f"aan (i.p.v. 2) - gebruik dat aantal, L/R op kanaal 0/1, "
                      f"rest stil.")
                self._out_channels = max_ch
        except Exception as e:
            print(f"[NICAM decoder] kon apparaat-samplerate/kanalen niet "
                  f"opvragen ({e}), val terug op native_samplerate="
                  f"{self._native_sr} Hz, 2 kanalen.")

        self._native_sr = actual_sr
        g = math.gcd(32000, self._native_sr)
        self._resample_up = self._native_sr // g
        self._resample_down = 32000 // g

        try:
            self._stream = sd.OutputStream(
                samplerate=self._native_sr,
                channels=self._out_channels,
                dtype='float32',
                device=device,
                callback=self._on_audio_output_needed,
                blocksize=0,
            )
            self._stream.start()
            print(f"[NICAM decoder] audio-uitvoer gestart @ {self._native_sr} Hz, "
                  f"resample vanaf 32000 Hz (up={self._resample_up}, "
                  f"down={self._resample_down}).")
        except Exception as e:
            print(f"[NICAM decoder] WAARSCHUWING: kon audio-uitvoer niet "
                  f"starten ({e}) - geen geluid.")
            self._stream = None

    def _on_audio_output_needed(self, outdata, frames, time_info, status):
        """Draait in PortAudio's eigen achtergrondthread. Haalt klaar-
        liggende samples uit de jitterbuffer; vult aan met stilte (en
        telt een underrun) als er niet genoeg klaarligt - het afspelen
        mag NOOIT wachten op de decoder."""
        with self._out_lock:
            outdata[:, :] = 0.0  # eerst alles stil - vooral belangrijk voor
                                  # kanalen 2+ bij apparaten met >2 kanalen,
                                  # want outdata is niet gegarandeerd leeg
            n = min(frames, len(self._out_buf_a))
            if n < frames:
                self._out_underruns += 1
            for i in range(n):
                outdata[i, 0] = self._out_buf_a.popleft()
                if self._out_channels > 1:
                    outdata[i, 1] = self._out_buf_b.popleft()
                else:
                    self._out_buf_b.popleft()  # mono apparaat: R-kanaal weggooien

    # ==================================================================
    # STAP D7: de-emphasis - initialisatie (exacte inverse van encoder's
    # J.17 pre-emphasis-filter: num/den omgewisseld = 1/H(z))
    # ==================================================================
    def _init_deemphasis(self, apply_deemphasis):
        self._deemphasis_enabled = bool(apply_deemphasis)
        f_zero, f_pole, gain0 = 477.15, 4132.27, 1.1030
        w_z, w_p = 2 * np.pi * f_zero, 2 * np.pi * f_pole
        preemph_b, preemph_a = bilinear([gain0 / w_z, gain0], [1.0 / w_p, 1.0], 32000)
        # inverse filter: H_deemph(z) = 1 / H_preemph(z) => teller/noemer omdraaien
        self._deemph_b, self._deemph_a = preemph_a, preemph_b
        self._deemph_state_a = np.zeros(max(len(self._deemph_b), len(self._deemph_a)) - 1)
        self._deemph_state_b = np.zeros(max(len(self._deemph_b), len(self._deemph_a)) - 1)

    def _apply_deemphasis(self, a_samples, b_samples):
        if not self._deemphasis_enabled or len(a_samples) == 0:
            return a_samples, b_samples
        a, self._deemph_state_a = lfilter(self._deemph_b, self._deemph_a, a_samples, zi=self._deemph_state_a)
        b, self._deemph_state_b = lfilter(self._deemph_b, self._deemph_a, b_samples, zi=self._deemph_state_b)
        return a.astype(np.float32), b.astype(np.float32)

    # ==================================================================
    # STAP D1: framesynchronisatie - initialisatie
    # ==================================================================
    def _init_frame_sync(self, lock_confirm_frames, lock_loss_frames):
        self._bitbuf = np.zeros(0, dtype=np.uint8)
        self._locked = False
        self._miss_streak = 0
        self._lock_confirm_frames = int(lock_confirm_frames)
        self._lock_loss_frames = int(lock_loss_frames)
        self._search_cap = 8 * 728          # max. bits die we bufferen tijdens zoeken
        self._search_min = (lock_confirm_frames + 1) * 728

        # scramble-reeks is deterministisch en elke frame identiek (reset
        # bij elke FAW) - zie epy_block_nicam_final.py STAP 7
        self._scramble_seq = self._make_scramble_sequence()

        # inverse permutatie van de encoder-interleave, eenmalig
        inv_idx = np.empty(704, dtype=np.int64)
        inv_idx[self._ENC_INTERLEAVE_IDX] = np.arange(704)
        self._deinterleave_idx = inv_idx

    @staticmethod
    def _make_scramble_sequence():
        """Identiek aan encoder's _make_scramble_sequence()."""
        state = [1] * 9
        bits = np.zeros(720, dtype=np.uint8)
        for i in range(720):
            fb = state[4] ^ state[8]
            state = [fb] + state[:-1]
            bits[i] = fb
        return bits

    def _try_acquire_lock(self):
        """Correleert over alle 728 mogelijke bit-offsets, kijkt welke
        offset de FAW het meest consistent laat terugkomen over meerdere
        opeenvolgende frames, en vergrendelt daarop als de score goed
        genoeg is."""
        buf = self._bitbuf
        check_frames = self._lock_confirm_frames
        needed = check_frames * 728 + 8
        if len(buf) < needed:
            return False

        best_offset, best_score = 0, -1.0
        for offset in range(728):
            total = 0
            for k in range(check_frames):
                start = offset + k * 728
                total += int(np.sum(buf[start:start + 8] == self.FAW_BITS))
            score = total / (8.0 * check_frames)
            if score > best_score:
                best_offset, best_score = offset, score

        if best_score >= 0.90:
            self._bitbuf = buf[best_offset:]
            self._locked = True
            self._miss_streak = 0
            self._lock_events += 1
            print(f"[NICAM decoder] frame-lock verkregen (score={best_score:.2f})")
            return True

        # geen lock gevonden - buffer beperkt houden, verder wachten op data
        if len(self._bitbuf) > self._search_cap:
            self._bitbuf = self._bitbuf[-self._search_cap:]
        return False

    # ==================================================================
    # STAP D5: schaalfactor terugwinnen (meerderheidsstem)
    # ==================================================================
    @staticmethod
    def _majority(bits):
        return int(np.mean(bits) > 0.5)

    def _recover_scale_factors(self, flip_received):
        R2A = self._majority(flip_received[0:49:6])
        R2B = self._majority(flip_received[1:50:6])
        R1A = self._majority(flip_received[2:51:6])
        R1B = self._majority(flip_received[3:52:6])
        R0A = self._majority(flip_received[4:53:6])
        R0B = self._majority(flip_received[5:54:6])
        rA = (R2A << 2) | (R1A << 1) | R0A
        rB = (R2B << 2) | (R1B << 1) | R0B
        e_a = self.CODE_TO_E.get(rA, 0)
        e_b = self.CODE_TO_E.get(rB, 0)
        return e_a, e_b

    # ==================================================================
    # STAP D6: decompanderen (exacte inverse van encoder's _compand_block)
    # ==================================================================
    @staticmethod
    def _decompand_block(compressed10, e):
        sign = (compressed10 >> 9) & 1
        mag9 = (compressed10 & 0x1FF).astype(np.int32)
        mag_shifted = mag9 << (4 - e)
        redundant_mask = ((1 << e) - 1) << (13 - e) if e > 0 else 0
        redundant_val = np.where(sign == 1, redundant_mask, 0)
        s14 = (sign.astype(np.int32) << 13) | redundant_val | mag_shifted
        signed = np.where(s14 >= 8192, s14 - 16384, s14)
        return (signed.astype(np.float32) / 8191.0)

    # ==================================================================
    # STAP D2/D3/D4/D5/D6 samen: één frame (728 bits) -> 32+32 samples
    # ==================================================================
    def _decode_frame(self, frame_bits728):
        faw_ok = int(np.sum(frame_bits728[:8] == self.FAW_BITS)) >= 6  # tolerant voor 1-2 bitfouten

        # STAP D2: descramblen
        descrambled = frame_bits728[8:] ^ self._scramble_seq   # 720 bits

        # STAP D4: control-bits + additional data (nu niet verder gebruikt,
        # maar wel afgesplitst zodat je ze later kunt uitlezen, bv. C1C2C3
        # voor stereo/mono-detectie)
        control_bits = descrambled[0:5]
        payload_interleaved = descrambled[16:16 + 704]

        # STAP D3: de-interleaven
        payload = payload_interleaved[self._deinterleave_idx]

        # woorden uitpakken: 64 x 11 bits (10 magnitude + 1 pariteit)
        words = payload.reshape(64, 11)
        mag_bits = words[:, 0:10]
        parity_bits = words[:, 10]
        shifts = np.arange(10)
        interleaved10 = (mag_bits.astype(np.uint16) << shifts).sum(axis=1)

        top6 = (interleaved10 >> 4) & 0x3F
        flip_received = parity_bits ^ self.PARITY_LUT[top6]

        # STAP D5
        e_a, e_b = self._recover_scale_factors(flip_received)

        comp_a = interleaved10[0::2]  # 32 woorden, A-kanaal
        comp_b = interleaved10[1::2]  # 32 woorden, B-kanaal

        # STAP D6
        a_f = self._decompand_block(comp_a, e_a)
        b_f = self._decompand_block(comp_b, e_b)

        return a_f, b_f, faw_ok, control_bits

    # ==================================================================
    # Diagnostiek
    # ==================================================================
    def _init_diagnostics(self):
        self._out_underruns = 0
        self._lock_events = 0
        self._frames_decoded = 0
        self._faw_errors = 0
        self._last_report = 0

    def _maybe_report_status(self):
        if self._frames_decoded - self._last_report >= 5000:
            self._last_report = self._frames_decoded
            pct = 100.0 * self._faw_errors / max(1, self._frames_decoded)
            print(f"[NICAM decoder] status: {self._frames_decoded} frames, "
                  f"FAW-afwijkingen {pct:.2f}%, audio-underruns {self._out_underruns}, "
                  f"lock-events {self._lock_events}")

    # ==================================================================
    # GNU Radio scheduler-interface
    # ==================================================================
    def work(self, input_items, output_items):
        self._ensure_audio_output_started()
        new_bits = input_items[0]
        self._bitbuf = np.concatenate([self._bitbuf, new_bits])

        if not self._locked:
            self._try_acquire_lock()

        a_chunks, b_chunks = [], []
        if self._locked:
            while len(self._bitbuf) >= 728:
                frame = self._bitbuf[:728]
                self._bitbuf = self._bitbuf[728:]

                a_f, b_f, faw_ok, _ctrl = self._decode_frame(frame)
                a_chunks.append(a_f)
                b_chunks.append(b_f)
                self._frames_decoded += 1

                if faw_ok:
                    self._miss_streak = 0
                else:
                    self._miss_streak += 1
                    self._faw_errors += 1
                    if self._miss_streak >= self._lock_loss_frames:
                        self._locked = False
                        print(f"[NICAM decoder] frame-lock VERLOREN na "
                              f"{self._miss_streak} opeenvolgende FAW-fouten")
                        break

        if a_chunks:
            a_all = np.concatenate(a_chunks)
            b_all = np.concatenate(b_chunks)

            # STAP D7: de-emphasis, over de hele batch tegelijk (zelfde
            # reden als bij de encoder: lfilter() per klein blokje apart
            # aanroepen is veel duurder dan één keer over de hele batch)
            a_all, b_all = self._apply_deemphasis(a_all, b_all)

            # STAP D8: resample 32kHz -> native samplerate geluidskaart
            if self._resample_up != 1 or self._resample_down != 1:
                a_out = resample_poly(a_all, self._resample_up, self._resample_down)
                b_out = resample_poly(b_all, self._resample_up, self._resample_down)
            else:
                a_out, b_out = a_all, b_all

            a_out = np.clip(a_out * self._output_gain, -1.0, 1.0)
            b_out = np.clip(b_out * self._output_gain, -1.0, 1.0)

            with self._out_lock:
                self._out_buf_a.extend(a_out.tolist())
                self._out_buf_b.extend(b_out.tolist())

        self._maybe_report_status()
        return len(new_bits)

    def stop(self):
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
        return True
