# BPSK Real-Time Audio Transceiver (GNU Radio 3.10 & ADALM-PLUTO)

Dit project bevat een volledige **BPSK SDR Audio Transceiver** flowgraph gebouwd in **GNU Radio 3.10**, ontworpen om live audio via de ether te zenden en te ontvangen met behulp van de **ADALM-PLUTO (PlutoSDR)** op de 70cm amateurradioband (~439.6 MHz).

De transceiver maakt gebruik van een robuuste **gepakketteerde MPEG-TS stream over BPSK** met automatische klok- en carrier-synchronisatie, energie-dispersie (scrambling), CRC32-foutdetectie en slimme buffer-/tag-beveiliging tegen dataverlies en latentie.

---

## 🚀 Kenmerken & Functionaliteiten

* **Full-Duplex BPSK Modulatie/Demodulatie**:
  * **Zender (TX)**: Zet UDP MPEG-TS audio om naar BPSK-symbolen met Root-Raised Cosine (RRC) filtering en stuurt deze naar de PlutoSDR TX-poort.
  * **Ontvanger (RX)**: Ontvangt RF-signaal via PlutoSDR RX, voert RRC-filtering uit, Gardner Symbol Synchronization, Costas Loop carrier recovery en BPSK slicer.
* **Geïntegreerde Audio Stream Pipeline**:
  * **TX Side**: Automatische audio-capturing via **`ffmpeg`** (vanaf virtuele of fysieke geluidskaart zoals *VB-Audio Cable*) naar AAC/MPEG-TS over UDP (`127.0.0.1:1234`).
  * **RX Side**: Automatische weergave via **`ffplay`** vanuit de gedecodeerde UDP MPEG-TS stream (`127.0.0.1:12345`).
* **Slimme Embedded Python Blocks (`epy_block`)**:
  * **Buffer & Latency Control (`epy_block_0`)**: Converteert lossige UDP-PDU's naar een ononderbroken bytestroom met instelbare vulbyte (`0x55`) zodra de buffer leeg is. Beperkt de maximale vertraging tot een ingesteld aantal seconden.
  * **Tag Repair & Resilience (`epy_block_1`)**: Beveiliging tegen beschadigde `packet_len` tags. Injecteert synthetische tags bij signaalverlies om vastlopen van de stream in downstream blokken te voorkomen.
  * **GUI Subprocess Handlers (`epy_block_2` & `epy_block_3`)**: Start en beheert achtergrondprocessen voor `ffmpeg` en `ffplay` met één druk op de knop in de QT GUI.
* **Interactieve QT GUI Control**:
  * Schuifregelaars voor **Frequentie** (439.45 MHz - 439.85 MHz) en **RRC Bandbreedte/Roll-off**.
  * Directe knoppen om `ffmpeg` en `ffplay` te starten.
  * Live weergave van **BPSK Constellatie diagram**, **RF Spectrum analyzer** en **Tijddomein pakket waveforms**.

---

## 🏗️ Systeemarchitectuur

### 📤 Transmit (TX) Pipeline
```
[ Audio-In / Cable-C ] 
       │ (ffmpeg AAC/MPEG-TS UDP:1234)
       ▼
[ network_socket_pdu ] ➔ [ epy_block_0 (PDU -> Continuous Stream + Filler) ]
       │
       ▼
[ stream_to_tagged_stream ] ➔ [ CRC32 Generator ] ➔ [ Additive Scrambler (0x8A) ]
       │
       ▼
[ Protocol Formatter (Header) ] ➔ [ Tagged Stream Mux ]
       │
       ▼
[ BPSK Constellation Modulator ] ➔ [ RRC Filter ] ➔ [ PlutoSDR Sink (192.168.1.61) ]
```

### 📥 Receive (RX) Pipeline
```
[ PlutoSDR Source (192.168.1.62) ]
       │
       ▼
[ RRC Filter ] ➔ [ Symbol Sync (Gardner) ] ➔ [ Costas Loop (Carrier Sync) ]
       │
       ▼
[ Complex to Real & Binary Slicer ] ➔ [ Correlate Access Code ]
       │
       ▼
[ epy_block_1 (Tag Validator & Injector) ] ➔ [ Repack Bits (1b -> 8b) ]
       │
       ▼
[ Additive Descrambler ] ➔ [ CRC32 Check ] ➔ [ network_udp_sink (UDP:12345) ]
       │
       ▼
[ ffplay Playback ]
```

---

## 🛠️ Benodigdheden & Afhankelijkheden

### Software
1. **GNU Radio 3.10.x** (met QT GUI en `gr-iio` ondersteuning)
2. **Python 3.x** met de pakketten `numpy` en `pmt`
3. **FFmpeg** & **FFplay** geïnstalleerd en toegevoegd aan de systeem `PATH`
4. **VB-Audio Virtual Cable** (optioneel, voor het doorsturen van systeem-audio naar FFmpeg op Windows)

### Hardware
* **ADALM-PLUTO (PlutoSDR)** (1 of 2 apparaten voor duplex werking)
  * Standaard ingestelde IP-adressen in het project:
    * Zender (TX Sink): `192.168.1.61`
    * Ontvanger (RX Source): `192.168.1.62`

---

## ⚙️ Parameters & Instellingen

| Parameter | Standaardwaarde | Beschrijving |
| :--- | :--- | :--- |
| **RF Frequentie** | `439.6055 MHz` | Instelbaar via GUI slider (439.450 - 439.850 MHz) |
| **Sample Rate (SDR)** | `1.2 MSPS` | PlutoSDR Baseband Sample Rate |
| **Symbol Rate / SPS** | `10 ksps` / `4 sps` | Samples per symbol op BPSK niveau |
| **Pakketlengte (`pkt_len`)** | `256 bytes` | Payload grootte per frame vóór CRC/Header |
| **Scrambler Seed / Mask** | `0x7F` / `0x8A` | Bit whitening ter voorkoming van constante DC-offset |
| **UDP Ingang (TX)** | `127.0.0.1:1234` | Inkomende MPEG-TS audio van FFmpeg |
| **UDP Uitgang (RX)** | `127.0.0.1:12345` | Uitgaande MPEG-TS audio naar FFplay |

---

## 🚦 Hoe te gebruiken

1. **Open het project in GNU Radio Companion**:
   ```bash
   gnuradio-companion BPSKproject1.grc
   ```
2. **Controleer de PlutoSDR IP-adressen**:
   Pas in de blokken `iio_pluto_sink_0_0_0` en `iio_pluto_source_0` eventueel de IP-adressen aan naar jouw eigen PlutoSDR hardware.
3. **Start de Flowgraph**:
   Klik op de knop **Execute** (of druk op `F6`). Het QT GUI venster verschijnt.
4. **Start Zenden & Ontvangen**:
   * Klik in de QT GUI op **`Start ffmpeg (audio-encoder)`** om de audio-opname en streaming naar de zender te starten.
   * Klik in de QT GUI op **`Start ffplay`** om het afspelen van de ontvangen gedecodeerde audio te starten.
5. **Monitoren & Tunen**:
   * Bekijk het **Constellatie diagram** om de fase- en kloksynchronisatie (Costas loop & Symbol sync) te controleren.
   * Gebruik de sliders om de frequentie en RRC-filterbandbreedte live bij te sturen.

---

## 📜 Licentie & Auteursrecht

Dit project is beschikbaar voor vrij gebruik, onderwijs en radioamateur experimenten.
