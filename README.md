# ICSSI Digital Twin — Oldsmar WWTP

> Simulasi serangan siber terhadap sistem pengolahan air minum, berdasarkan **insiden nyata di Oldsmar, Florida, 8 Februari 2021**.

Dikembangkan oleh **Industrial Control System Security Indonesia (ICSSI)** untuk keperluan pelatihan dan edukasi keamanan siber sistem kontrol industri (ICS).

---

## Latar Belakang

Pada 8 Februari 2021, seorang peretas berhasil masuk ke sistem SCADA instalasi pengolahan air minum kota Oldsmar, Florida melalui software remote desktop. Dalam hitungan detik, ia mengubah kadar NaOH (soda api) dari **111 ppm menjadi 11.100 ppm** — seratus kali lipat batas aman.

Jika tidak segera dideteksi, air yang mengalir ke puluhan ribu warga kota akan bersifat sangat korosif dan berbahaya dikonsumsi. Seorang operator kebetulan melihat kursor mouse bergerak sendiri di layarnya, langsung mengenali serangan, dan mengembalikan setpoint secara manual.

**Repositori ini mereplikasi kejadian tersebut dalam lingkungan simulasi** — lengkap dengan sensor server, PLC, SCADA HMI, dan script serangan.

---

## Arsitektur

```
┌──────────────────┐  Modbus TCP   ┌──────────────┐  Modbus TCP   ┌──────────────┐
│  Sensor Server   │ ◄───────────► │   OpenPLC    │ ◄───────────► │  SCADA HMI   │
│  port 5020       │               │   port 502   │               │  (GUI)       │
└──────────────────┘               └──────────────┘               └──────────────┘
         ▲
         │  Modbus TCP
┌────────┴─────────┐
│  Attack Script   │  ← simulasi penyerang dari mesin terpisah
└──────────────────┘
```

| Komponen | File | Peran |
|----------|------|-------|
| Sensor Server | `sensors/sensor_server.py` | Simulasi fisika proses WWTP, expose via Modbus |
| PLC Logic | `openplc/wwtp_control.st` | Kontrol otomatis, alarm flags (IEC 61131-3 ST) |
| SCADA HMI | `scada/main.py` | Dashboard operator: P&ID, trend, alarm, kontrol |
| Attack Script | `attack/oldsmar_attack.py` | Mereplikasi serangan Oldsmar dari sisi penyerang |

---

## Cara Menjalankan

### Prasyarat

```bash
pip install -r requirements.txt
```

OpenPLC Runtime harus terinstall dan berjalan di `http://localhost:8080`.

### Urutan Start

```bash
# 1. Sensor Server
python sensors/sensor_server.py

# 2. Upload wwtp_control.st ke OpenPLC, konfigurasi slave device (lihat openplc/openplc_setup.md), lalu Start

# 3. SCADA HMI
python scada/main.py --host 127.0.0.1 --port 502

# 4. Script serangan (dari mesin lain, arahkan ke IP OpenPLC)
python attack/oldsmar_attack.py --host <IP_OPENPLC>
```

### Build ke EXE (Windows)

```bash
build.bat   # pilih: Sensor Server / SCADA / keduanya
```

Hasil: `dist/ICSSI_SensorServer.exe` dan `dist/ICSSI_SCADA.exe`

---

## Normal vs Serangan

### Kondisi Normal

Sistem berjalan stabil. Semua sensor hijau, tidak ada alarm.

| Parameter | Nilai Normal |
|-----------|:-----------:|
| pH | 7.20 |
| NaOH Setpoint | 111 ppm |
| NaOH Aktual | ~111 ppm |
| Flow In/Out | ~520 / ~505 L/menit |
| Chlorine | ~1.95 ppm |

### Saat Serangan

Setpoint NaOH berubah drastis → NaOH aktual naik → pH melonjak.

| Parameter | Normal | Diserang |
|-----------|:------:|:--------:|
| NaOH Setpoint | 111 ppm | **11.100 ppm** |
| NaOH Aktual | ~111 ppm | naik ke ribuan ppm |
| pH | 7.2 | naik ke 12–13 |
| Banner SCADA | — | **!! ATTACK DETECTED !!** |
| Alarm tiles | semua mati | HIGH NaOH, PH HIGH menyala |

> **Aturan praktis:** NaOH Setpoint tiba-tiba di atas 200 ppm tanpa perubahan manual = **tanda serangan**. Respons: tekan **E-STOP**, kembalikan setpoint ke 111.

---

## SCADA HMI

Tampilan retro enterprise bergaya Wonderware/Citect, dengan:

- **P&ID Diagram** — skema proses lengkap dengan animasi pompa
- **Digital Display** — nilai sensor real-time dengan bar status warna
- **Alarm Annunciator** — tile LED: `HIGH NaOH`, `PH HIGH`, `ATTACK DETECT`, dll
- **Trend Chart** — historis pH & NaOH (120 titik, ~2 menit)
- **Event Log** — log berwarna: merah (alarm), hijau (restore), kuning (warn)
- **Control Panel** — setpoint NaOH, toggle aktuator, tombol E-STOP

---

## Struktur Direktori

```
icssi-digital-twin/
├── sensors/
│   ├── sensor_server.py      # Modbus TCP server + loop simulasi
│   ├── physics.py            # Model fisika proses WWTP
│   └── config.py             # Register map & konstanta
├── openplc/
│   ├── wwtp_control.st       # Program PLC (Structured Text)
│   └── openplc_setup.md      # Panduan konfigurasi slave device
├── scada/
│   ├── main.py               # SCADA HMI (tkinter + Pillow)
│   ├── comms.py              # Modbus polling thread
│   ├── theme.py              # Warna & font
│   └── assets.py             # Generator gambar P&ID
├── attack/
│   └── oldsmar_attack.py     # Script serangan
├── build.bat                 # Build EXE
├── start_lab.bat             # Launcher lab
└── requirements.txt
```

---

## Referensi

- [CISA Alert AA21-042A — Oldsmar Water Treatment Facility](https://www.cisa.gov/news-events/cybersecurity-advisories/aa21-042a)
- IEC 61131-3 Structured Text Standard
- Modbus Application Protocol Specification V1.1b3

---

> **Peringatan:** Repositori ini hanya untuk penggunaan di lingkungan lab / cyber range yang terisolasi. Dilarang keras digunakan terhadap sistem nyata.

*ICSSI — Industrial Control System Security Indonesia*
