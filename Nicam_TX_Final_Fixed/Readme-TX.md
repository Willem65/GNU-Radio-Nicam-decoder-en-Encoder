# GNU Radio NICAM 728 Transmitter (TX)

Een geoptimaliseerde GNU Radio (v3.10+) DSP-flowgraph en bijbehorende Embedded Python Blocks voor het in real-time encoderen, moduleren (DQPSK) en uitzenden van digitale **NICAM 728** stereo-audio via een Software Defined Radio (zoals de ADALM-PLUTO)[cite: 10, 11, 12].

---

## Over dit project

Dit project implementeert de volledige NICAM 728 (ETS 300 163 / ITU-T J.17 / Repeater 4/1998) zendketen[cite: 10]. Live audio wordt via een eigen achtergrondthread ingelezen, doorloopt alle 9 coderingsstappen binnen één self-contained Python-bronblok om Windows/GNU Radio scheduler-dropouts te voorkomen, en wordt via een Root Raised Cosine filter naar de SDR gestuurd[cite: 10, 11, 12].

### Belangrijkste functionaliteiten

* **All-in-One Audio Framer Architecture:** Alle audio-opname, resampling, buffering, filtering en framing draaien binnen één blok in een eigen achtergrondthread via PortAudio (`sounddevice`)[cite: 10]. Dit voorkomt carrier-dropouts en buffer-underruns[cite: 10].
* **Live IQ-Inversie Toggle:** Een GUI-drukknop maakt het mogelijk om live de $Q$-component te spiegelen ($Q = -Q$) ter compensatie van boven- of ondermenging door een externe RF-mixer[cite: 11, 12, 13].
* **Conform ETS 300 163 & ITU-T J.17:**
  * CCITT / ITU-T J.17 pre-emphasis filter[cite: 10].
  * 12 kHz Butterworth laagdoorlaatfilter tegen aliasing[cite: 10].
  * 14-bit linear naar 10-bit near-instantaneous companding met schaalfactor-overdracht via pariteit[cite: 10].
  * Bit-interleaving en 9-bit LFSR energy-dispersal scrambling[cite: 10].
  * Continuous-phase DQPSK modulatie (364 symbolen per frame)[cite: 10].
* **Hardware-integratie:** Direct afgestemd op de ADALM-PLUTO op IP-adres `192.168.1.61` met 8 dB attenuatie en 1.2 MHz RF-bandbreedte[cite: 11, 12].

---

## Signaalketen (Signal Chain)

```text
[ Live Audio Invoer (PortAudio / WASAPI / DirectSound) ]
       │
       ▼
[ NICAM 728 Encoder (All-in-One Block) ] 
  ├─ 1. Resampling naar 32 kHz
  ├─ 2. 12 kHz Laagdoorlaatfilter
  ├─ 3. ITU-T J.17 Pre-emphasis
  ├─ 4. 14-bit -> 10-bit Companding
  ├─ 5. Frame-opbouw (FAW, C0-C4, AD)
  ├─ 6. Bit-interleaving
  ├─ 7. LFSR Scrambling (x^9 + x^4 + 1)
  └─ 8. DQPSK Modulatie (364 symbolen/frame)
       │
       ▼ (Complex64 DQPSK Stream @ 728 kS/s)
[ Root Raised Cosine Filter ] ─── (Interp=2, Alpha=1.0 / 100% Roll-off @ System I)
       │
       ▼
[ IQ Invert Toggle ] ──────────── (QT GUI Button: Q = -Q)
       │
       ├──────────────────────────► [ QT GUI Constellation Sink ]
       ▼
[ PlutoSDR Sink (192.168.1.61) ] ──► (TX Freq: 478 MHz + Trim)
```[cite: 10, 11, 12, 13]

---

## De 9 Coderingsstappen in de Encoder (`nicam_tx_minimal_epy_block_nicam_final.py`)

1. **STAP 0: Audio-inname:** PortAudio achtergrondthread leest live stereo-audio in zonder de GNU Radio scheduler-thread te blokkeren[cite: 10].
2. **STAP 1: Resampling:** Polyfase resampling (`resample_poly`) van de native samplerate (bijv. 48 kHz) naar de voor NICAM vereiste 32.000 Hz[cite: 10].
3. **STAP 2: Band-begrenzing:** 4e-orde Butterworth laagdoorlaatfilter op 12 kHz om HF-ruis en aliasing te elimineren[cite: 10].
4. **STAP 3: J.17 Pre-emphasis:** Pas het officiële ITU-T J.17 shelf-filter toe (+6.5 dB boost bij 800 Hz)[cite: 10].
5. **STAP 4: Kwantisatie & Companding:** Zet 32 audio-samples om van 14-bit naar 10-bit met dynamisch gekozen schaalfactor-exponent $e$ (0..4) per ms[cite: 10].
6. **STAP 5: Frame-opbouw:** Samenvoegen van het 8-bit Frame Alignment Word (`01001110`), 5 besturingsbits ($C_0..C_4$), 11 gereserveerde bits en 64 geinterleaved geluidswoorden van 11 bits (inclusief signalling-in-parity)[cite: 10].
7. **STAP 6: Bit-interleaving:** Permutatie van de 704 databits over een 44x16 matrix om burst-fouten op het RF-pad te spreiden[cite: 10].
8. **STAP 7: Scrambling:** XOR-operatie van 720 bits met een 9-bit LFSR pseudo-random generator ($x^9 + x^4 + 1$), gereset bij elke FAW[cite: 10].
9. **STAP 8: DQPSK Modulatie:** Omzetten van 728 bits naar 364 DQPSK-symbolen met doorlopende fase-accumulatie ($0^\circ, -90^\circ, -270^\circ, -180^\circ$)[cite: 10].

---

## Parameteroverzicht (`nicam_tx_minimal.grc`)

| Parameter | Waarde | Omschrijving |
| :--- | :--- | :--- |
| **`samp_rate`** | `728000` Hz | Symboolsnelheid ($364.000 \text{ sym/s} \times \text{sps}(2)$)[cite: 11, 12]. |
| **`sps`** | `2` | Samples per symbool[cite: 11, 12]. |
| **`rrc_alpha`** | `1.0` | 100% Roll-off (specifiek voorgeschreven voor 6.552 MHz Systeem I draaggolven)[cite: 10, 11, 12]. |
| **`rrc_gain`** | `0.5` | Versterking van het RRC-filter[cite: 11, 12]. |
| **`tx_freq`** | `478000000` Hz | Pluto zendfrequentie (voorinstelling voor externe RF-upconverter naar 6.552 MHz)[cite: 11, 12]. |
| **Pluto URI** | `192.168.1.61` | IP-adres van de zendende PlutoSDR[cite: 11, 12]. |

---

## Vereisten & Installatie

### Software-afhankelijkheden

* **GNU Radio:** `v3.10.0` of hoger
* **Python bibliotheken:**
  ```bash
  pip install numpy scipy sounddevice
  ```[cite: 10]
* **SDR Drivers:** `gr-iio` / `libiio` voor ADALM-PLUTO ondersteuning[cite: 11, 12].

### Bestanden in deze repository

* **`nicam_tx_minimal.grc`**: Het GNU Radio Companion bronbestand van de TX-flowgraph[cite: 11].
* **`nicam_tx_minimal.py`**: Het gegenereerde Python-script van de flowgraph[cite: 12].
* **`nicam_tx_minimal_epy_block_nicam_final.py`**: Het Embedded Python Block met de volledige DSP- en audio-encoder[cite: 10, 12].
* **`nicam_tx_minimal_epy_block_iq_invert.py`**: Het Embedded Python Block voor live IQ-fase inversie[cite: 12, 13].

---

## Gebruik

1. Open de repository in een terminal:
   ```bash
   cd GNU-Radio-Nicam-decoder-en-Encoder