# GNU Radio NICAM 728 Receiver & Decoder

Een complete GNU Radio (v3.10+) DSP-flowgraph en bijbehorende Embedded Python Blocks voor het in real-time ontvangen, demoduleren (DQPSK) en decoderen van digitale **NICAM 728** stereo-audio via een Software Defined Radio (zoals de ADALM-PLUTO)[cite: 6, 7, 8, 9].

---

## Over dit project

Dit project implementeert de volledige NICAM 728 (ETS 300 163 / ITU-T J.17) ontvangst- en de-coderingspijplijn[cite: 6, 8]. Het signaal wordt opgevangen via een SDR, gedemoduleerd naar een ruwe bitstroom en verwerkt door een custom Python-blok dat live stereo-audio afspeelt via de geluidskaart[cite: 6, 8, 9].

### Belangrijkste functionaliteiten

* **SDR Hardware-integratie:** Afgestemd op de ADALM-PLUTO (PlutoSDR) op IP-adres `192.168.1.62` met een standaardsamplerate van 728 kS/s[cite: 8, 9].
* **Live IQ-Inversie Toggle:** Een ingebouwd GUI-commando stelt je in staat om direct de $Q$-component te spiegelen ($Q = -Q$) om frequentie-inversie door externe mixers te compenseren[cite: 7, 8, 9].
* **Robuuste Framesynchronisatie:** Automatische FAW-detectie (*Frame Alignment Word*) met instelbare confirmatie- en verliesdrempels[cite: 6, 8].
* **Volledige NICAM-728 De-codering:**
  * Descrambling via een 9-bit LFSR-generator[cite: 6, 8].
  * Inverse permutatie (de-interleaving) van het 704-bit payload-blok[cite: 6, 8].
  * Schaalfactor-herstel via meerderheidsstemming over de pariteitsbits[cite: 6, 8].
  * 10-bit magnitude + schaalfactor decompandering naar 14-bit lineaire audio[cite: 6, 8].
  * Inverse J.17 de-emphasis filtering[cite: 6, 8].
* **Real-time Audio Afspelen:** Draait in een achtergrondthread via PortAudio (`sounddevice`) met automatische resampling (32 kHz naar 48 kHz / native geluidskaartsamplerate) en een jitterbuffer om underruns te voorkomen[cite: 6, 8, 9].

---

## Signaalketen (Signal Chain)

```text
[ Pluto SDR RX (192.168.1.62) ] ── (728 kS/s @ 477.9995 MHz)
       │
       ▼
[ IQ Invert Toggle ] ──────────── (QT GUI Button: Q = -Q)
       │
       ▼
[ Root Raised Cosine Filter ] ─── (Decim=1, Interp=2, Gain=1.3, BW=1.5)
       │
       ▼
[ Symbol Sync ] ───────────────── (Gardner TED, 2 SPS, Damping=1.414)
       │
       ▼
[ Costas Loop ] ───────────────── (4th Order, Loop BW=0.6) ──► [ Constellation Sink ]
       │
       ▼
[ Constellation Decoder ] ─────── (QPSK Constellation) ─────► [ File Sink: voor_diff.ts ]
       │
       ▼
[ Map Bits ] ──────────────────── (Map: [1, 2, 0, 3])
       │
       ▼
[ Differential Decoder ] ──────── (Modulus 4) ──────────────► [ File Sink: na_diff.ts ]
       │
       ▼
[ Map Bits ] ──────────────────── (Map: [0, 2, 3, 1])
       │
       ▼
[ Unpack K Bits ] ─────────────── (K = 2 bits per symbol)
       │
       ▼
[ NICAM 728 Decoder ] ────────── (Embedded Python Block)
       │
       ▼
[ Geluidskaart / PortAudio ] ──── (Stereo Audio Output @ 48 kHz)
```[cite: 6, 7, 8, 9]

---

## Technische Specificaties & Parameters

### Flowgraph Instellingen (`DQPSKproject1.grc`)

| Parameter | Waarde | Omschrijving |
| :--- | :--- | :--- |
| **`samp_rate`** | `728000` Hz | Symboolsnelheid van het NICAM-signaal (728 kbit/s)[cite: 6, 8, 9]. |
| **`sps`** | `2` | Samples per symbool[cite: 8, 9]. |
| **`freq_tune`** | `477999500` Hz | Standaard draaggolffrequentie (instelbaar via slider van 477 tot 479.7 MHz)[cite: 8, 9]. |
| **`Fil_Gain`** | `1.3` | Versterking van het Root Raised Cosine filter[cite: 8, 9]. |
| **`BW_tune`** | `1.5` | Bandbreedte/roll-off van het RRC-filter[cite: 8, 9]. |
| **Pluto URI** | `192.168.1.62` | IP-adres van de PlutoSDR[cite: 8, 9]. |

---

## De 8 Stappen van de NICAM 728 Decoder (`DQPSKproject1_epy_block_0_1_0.py`)

1. **STAP D1: Framesynchronisatie:** Zoekt continu naar het 8-bit Frame Alignment Word (`01001110`) in de binnenkomende bitstroom[cite: 6, 8]. Bij 3 opeenvolgende FAW-matches vergrendelt het blok de frame-lock[cite: 6, 8].
2. **STAP D2: Descramblen:** Voert een XOR-operatie uit over de 720 payload-bits met de genormeerde 9-bit LFSR pseudo-random generator-reeks[cite: 6, 8].
3. **STAP D3: De-interleaven:** Voert de inverse permutatie uit over de 704 databits om de oorspronkelijke 64 woorden van 11 bits te herstellen[cite: 6, 8].
4. **STAP D4: Controle-bits Uitlezen:** Splitst de 5 besturingsbits (`C1`, `C2`, `C3`, etc.) af van het frame[cite: 6, 8].
5. **STAP D5: Schaalfactor-herstel:** Bepaalt de schaalfactoren $e_A$ en $e_B$ (voor A- en B-kanaal) via een meerderheidsstemming over 9 pariteitsbits per kanaal[cite: 6, 8].
6. **STAP D6: Decompanderen:** Converteert de 10-bit gecompandeerde mantissa met behulp van de schaalfactor terug naar 14-bit lineaire audio-samples[cite: 6, 8].
7. **STAP D7: De-emphasis Filtering:** Past de exacte inverse toe van de ITU-T J.17 pre-emphasis filtercurve ($1 / H_{pre}(z)$) via `scipy.signal.lfilter`[cite: 6, 8].
8. **STAP D8: Resampling & Audio Afspelen:** Resamplet de 32 kHz NICAM-audio via `resample_poly` naar de native samplerate van de geluidskaart (bijv. 48 kHz) en stuurt dit direct naar de speakers via PortAudio[cite: 6, 8].

---

## Vereisten & Installatie

### Software-afhankelijkheden

* **GNU Radio:** `v3.10.0` of hoger[cite: 8, 9]
* **Python bibliotheken:**
  ```bash
  pip install numpy scipy sounddevice
  ```[cite: 6, 8]
* **SDR Drivers:** `gr-iio` / `libiio` voor de ADALM-PLUTO ondersteuning[cite: 8, 9].

### Bestanden in deze repository

* **`DQPSKproject1.grc`**: Het bronbestand van de GNU Radio Companion flowgraph[cite: 8].
* **`DQPSKproject1.py`**: Het gecompileerde Python-script van de flowgraph.
* **`DQPSKproject1_epy_block_0_1_0.py`**: Het Embedded Python Block voor de NICAM-728 framing en decodering[cite: 6, 8, 9].
* **`DQPSKproject1_epy_block_iq_invert.py`**: Het Embedded Python Block voor de IQ-fase inversie knop[cite: 7, 8, 9].

---

## Gebruik

1. Kloon de repository:
   ```bash
   git clone [https://github.com/Willem65/GNU-Radio-Nicam-decoder-en-Encoder.git](https://github.com/Willem65/GNU-Radio-Nicam-decoder-en-Encoder.git)
   cd GNU-Radio-Nicam-decoder-en-Encoder