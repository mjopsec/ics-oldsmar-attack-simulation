# ICSSI Digital Twin — Oldsmar WWTP ICS Cyber Range

Simulasi digital twin sistem pengolahan air minum (WWTP) berbasis insiden nyata **Oldsmar, Florida, 8 Februari 2021**, dikembangkan oleh **Industrial Control System Security Indonesia (ICSSI)** untuk keperluan pendidikan dan latihan keamanan siber ICS.

---

## Kondisi Normal vs Kondisi Serangan

> Bagian ini menjelaskan secara sederhana apa yang terjadi pada sistem pengolahan air ketika beroperasi normal dan ketika sedang diserang — sehingga operator atau peserta latihan dapat mengenali serangan hanya dari melihat nilai-nilai di layar SCADA.

---

### Proses Pengolahan Air Minum (Singkat)

Air mentah masuk ke instalasi pengolahan. Di dalam, beberapa zat kimia ditambahkan:
- **NaOH (Sodium Hydroxide / Soda Api)** — digunakan untuk menetralkan pH air agar tidak terlalu asam
- **Klorin** — untuk membunuh bakteri sebelum air didistribusikan ke masyarakat

Semua proses ini dikendalikan oleh sistem komputer (PLC + SCADA). Jika seseorang dapat membobol sistem ini dan mengubah parameter tanpa izin, akibatnya bisa sangat berbahaya.

---

### Kondisi Normal

Ketika sistem berjalan normal, semua nilai sensor berada dalam rentang aman berikut:

| Parameter | Nilai Normal | Rentang Aman | Satuan |
|-----------|:-----------:|:------------:|--------|
| **pH Air** | 7.20 | 6.5 – 8.5 | — (skala 0-14) |
| **NaOH Setpoint** | 111 | < 200 | ppm |
| **NaOH Aktual** | ~111 | < 200 | ppm |
| **Flow In** | ~520 | > 200 | L/menit |
| **Flow Out** | ~505 | > 200 | L/menit |
| **Water Level** | ~210 | 80 – 280 | cm |
| **Turbiditas** | ~1.2 | < 5 | NTU (kejernihan) |
| **Suhu** | ~21.5 | 15 – 30 | °C |
| **Klorin** | ~1.95 | 0.5 – 4 | ppm |
| **Tekanan** | ~44.8 | 20 – 70 | PSI |

**Tampilan SCADA saat normal:**
- Semua bar sensor berwarna **hijau**
- Tidak ada tile alarm yang menyala di panel Alarm Annunciator
- Tidak ada banner merah di bagian atas layar
- Event log menampilkan pesan `[INFO]` berwarna abu-abu

---

### Apa Itu Serangan Oldsmar?

Pada **8 Februari 2021**, sistem SCADA instalasi pengolahan air kota Oldsmar, Florida (AS) dibobol oleh peretas tak dikenal melalui software remote desktop (TeamViewer).

Penyerang **mengubah setpoint NaOH dari 111 ppm menjadi 11.100 ppm** — meningkat **100 kali lipat** dalam hitungan detik.

Jika tidak segera dideteksi:
- Konsentrasi NaOH di dalam air akan terus naik
- pH air meningkat ekstrem (hingga 13+) — air menjadi sangat basa/korosif
- Air berbahaya untuk dikonsumsi dan dapat merusak jaringan perpipaan
- Dampak potensial: ribuan warga kota yang meminum air terkontaminasi

Seorang operator kebetulan melihat **kursor mouse bergerak sendiri** di layar, segera menyadari ada yang tidak beres, dan mengembalikan setpoint secara manual.

---

### Kondisi Saat Diserang

Begitu serangan terjadi, nilai-nilai di SCADA mulai berubah secara tidak normal:

#### Perubahan Langsung (0 – 10 detik pertama)

| Parameter | Sebelum Serangan | Sesudah Serangan | Perubahan |
|-----------|:----------------:|:----------------:|-----------|
| **NaOH Setpoint** | 111 ppm | **11.100 ppm** | ⬆ naik 100× |
| NaOH Aktual | ~111 ppm | mulai naik... | ⬆ terus naik |
| pH | ~7.20 | masih ~7.20 | belum berubah |

> Perubahan setpoint adalah **tanda serangan paling awal dan paling jelas**. Setpoint tidak akan berubah sendiri dalam operasi normal.

#### Dampak Berikutnya (10 – 60 detik)

| Parameter | Nilai Normal | Saat Diserang | Keterangan |
|-----------|:-----------:|:-------------:|-----------|
| **NaOH Setpoint** | 111 ppm | **11.100 ppm** | Tetap tinggi selama serangan berlangsung |
| **NaOH Aktual** | ~111 ppm | **500 – 5.000 ppm** | Naik terus mengikuti setpoint |
| **pH** | 7.20 | **9.0 – 12.0** | Naik karena NaOH bersifat basa |
| NaOH Tank | ~80% | turun cepat | Tangki NaOH terkuras |
| Klorin | ~1.95 ppm | berubah | Keseimbangan kimia terganggu |

#### Kondisi Kritis (> 60 detik tanpa tindakan)

| Parameter | Nilai Kritis | Arti |
|-----------|:-----------:|------|
| **NaOH Aktual** | **> 5.000 ppm** | 45× di atas batas aman |
| **pH** | **> 12** | Air korosif, berbahaya diminum |
| **NaOH Setpoint** | **11.100 ppm** | Target serangan Oldsmar tercapai |
| NaOH Tank | mendekati 0% | Tangki NaOH hampir habis |

---

### Cara Membaca SCADA Saat Serangan

```
Kondisi Normal:              Kondisi Diserang:
┌─────────────────────┐      ┌─────────────────────────────────────┐
│  ░░░░░░░░░░ 7.20    │ pH   │  ████████████████████████ 12.5  ⚠  │
│  ▓▓▓▓░░░░░░ 111 ppm │ NaOH │  ████████████████████████ 8500 ppm ⚠│
│  [semua hijau]      │      │  [merah, alarm menyala]             │
└─────────────────────┘      └─────────────────────────────────────┘
```

**Sinyal visual serangan di SCADA:**

| Elemen SCADA | Kondisi Normal | Kondisi Diserang |
|-------------|---------------|-----------------|
| **Banner Title Bar** | *(kosong)* | **`!! ATTACK DETECTED !!`** merah berkedip |
| **Bar NaOH Setpoint** | hijau, ~111 | merah, angka besar (> 500) |
| **Bar pH** | hijau, 6.5–8.5 | merah/kuning, > 8.5 |
| **Bar NaOH Aktual** | hijau, < 200 | merah, naik terus |
| **Tile ATTACK DETECT** | abu-abu gelap | **merah menyala** |
| **Tile HIGH NaOH** | abu-abu gelap | **merah menyala** |
| **Tile PH HIGH** | abu-abu gelap | **merah menyala** |
| **Trend Chart** | garis datar/stabil | **garis naik tajam** |
| **Event Log** | pesan INFO abu-abu | **pesan ALARM merah** |

---

### Timeline Serangan & Respons Operator

```
t=0s    Penyerang berhasil masuk ke sistem
        → NaOH Setpoint berubah: 111 ppm → 11.100 ppm
        → Banner ATTACK DETECTED muncul di SCADA
        → Event log: [ALARM] NaOH setpoint anomaly: 11100 ppm

t=5s    Pompa dosing terus memompa NaOH dengan laju 100×
        → NaOH Aktual mulai naik
        → Trend chart menunjukkan kenaikan tajam

t=15s   NaOH Aktual melewati 200 ppm
        → Tile HIGH NaOH menyala merah
        → pH mulai meningkat di atas 8.5
        → Tile PH HIGH menyala merah

t=30s   NaOH Aktual ~2.500 ppm, pH ~11
        → Sistem dalam kondisi berbahaya

t=60s   NaOH Aktual ~8.000–10.000 ppm, pH ~12–13
        → Air sudah tidak aman untuk distribusi

─── RESPONS YANG BENAR ────────────────────────────────────────────
Operator melihat anomali → Klik E-STOP di SCADA
        → Semua pompa berhenti
        → NaOH Aktual mulai turun (dilusi)
        → Kembalikan setpoint ke 111 ppm
        → pH perlahan kembali normal
```

---

### Ringkasan: Apa yang Membedakan Normal vs Serangan

| | Normal | Diserang |
|--|:------:|:--------:|
| NaOH Setpoint | **111 ppm** | **> 500 ppm** (hingga 11.100) |
| NaOH Aktual | stabil ~111 ppm | **naik terus** |
| pH | stabil 7.0–7.5 | **naik di atas 8.5** |
| Trend Chart | garis mendatar | **garis naik tajam** |
| Alarm tiles | semua mati | **beberapa menyala merah** |
| Banner merah | tidak ada | **ATTACK DETECTED** |

> **Aturan praktis:** Jika nilai **NaOH Setpoint tiba-tiba jauh di atas 200 ppm** tanpa ada perubahan manual dari operator, itu adalah tanda serangan. Tindakan pertama: tekan **E-STOP** untuk menghentikan semua pompa, lalu investigasi.

---

## Arsitektur Sistem

```
┌─────────────────┐    Modbus TCP     ┌─────────────────┐    Modbus TCP     ┌─────────────────┐
│  Sensor Server  │ ◄────────────── ► │    OpenPLC      │ ◄────────────── ► │   SCADA HMI     │
│  (port 5020)    │   slave device    │   (port 502)    │   Modbus client   │   (port 502)    │
│                 │                   │                  │                   │                  │
│ • Simulasi fisika│                  │ • ST logic       │                   │ • Visualisasi    │
│ • 11 sensor IR  │                   │ • Alarm logic    │                   │ • P&ID diagram   │
│ • Coil aktuator │                   │ • Setpoint init  │                   │ • Event log      │
└─────────────────┘                   └─────────────────┘                   └─────────────────┘
        ▲
        │ Modbus TCP (port 502)
┌───────┴─────────┐
│  Attack Script  │  ← Komputer penyerang (terpisah)
│  (oldsmar_attack│
│    .py)         │
└─────────────────┘
```

### Alur Data

| Layer | Komponen | Peran |
|-------|----------|-------|
| Field Device | `sensors/sensor_server.py` | Simulasi sensor fisika WWTP |
| PLC | OpenPLC Runtime | Logika kontrol IEC 61131-3 |
| HMI/SCADA | `scada/main.py` | Monitoring operator |
| Attacker | `attack/oldsmar_attack.py` | Simulasi serangan dari mesin terpisah |

---

## Peta Register Modbus

### Sensor Server (port 5020) — sebagai Modbus Server

| Register | Alamat | Isi | Skala |
|----------|--------|-----|-------|
| Input Register 0 | IR 0 | pH | ×100 (720 = 7.20) |
| Input Register 1 | IR 1 | Flow In (L/min) | 1:1 |
| Input Register 2 | IR 2 | NaOH Tank Level (%) | 1:1 |
| Input Register 3 | IR 3 | Water Level (cm) | 1:1 |
| Input Register 4 | IR 4 | Turbidity (NTU) | ×10 |
| Input Register 5 | IR 5 | Temperature (°C) | ×10 |
| Input Register 6 | IR 6 | Chlorine (ppm) | ×100 |
| Input Register 7 | IR 7 | Pressure (PSI) | ×10 |
| Input Register 8 | IR 8 | NaOH Aktual (ppm) | ×10 |
| Input Register 9 | IR 9 | Alarm Bitmask | — |
| Input Register 10 | IR 10 | Flow Out (L/min) | 1:1 |
| Holding Register 0 | HR 0 | NaOH Setpoint (ppm) | 1:1 |
| Holding Register 1 | HR 1 | Chlorine Setpoint | ×100 |
| Holding Register 2 | HR 2 | Flow Setpoint (L/min) | 1:1 |
| Holding Register 3 | HR 3 | Pump Speed (%) | 1:1 |
| Coil 0–4 | CO 0–4 | Aktuator (main/dosing/outlet/estop/chlor) | bool |

### OpenPLC (port 502) — setelah slave device mapping

| IEC Address | Modbus Address | Isi |
|-------------|---------------|-----|
| %IW100–%IW110 | IR 100–110 | Semua sensor (urutan sama di atas) |
| %QW100–%QW103 | HR 100–103 | Setpoint |
| %QX100.0–100.4 | Coil 800–804 | Aktuator |

---

## Cara Menjalankan

### Prasyarat

```bash
pip install pymodbus tkinter pillow
```

OpenPLC Runtime harus terinstal dan berjalan di `http://localhost:8080`.

### Urutan Start

**1. Jalankan Sensor Server**
```bash
python sensors/sensor_server.py
```

**2. Upload & jalankan program OpenPLC**
- Buka `http://localhost:8080`
- Upload `openplc/wwtp_control.st`
- Konfigurasi slave device (lihat `openplc/openplc_setup.md`)
- Start program

**3. Jalankan SCADA (komputer operator)**
```bash
python scada/main.py --host 127.0.0.1 --port 502
```

**4. Jalankan serangan (komputer penyerang)**
```bash
python attack/oldsmar_attack.py --host <IP_OPENPLC>
python attack/oldsmar_attack.py --mode auto     # langsung serang
python attack/oldsmar_attack.py --mode restore  # pulihkan
```

### Script Launcher

```bash
start_lab.bat   # Windows launcher dengan menu interaktif
```

---

## Fitur SCADA HMI

### Tampilan Umum

SCADA menggunakan desain **retro enterprise** dengan palet warna navy-biru, tanpa warna hitam murni. Dirancang menyerupai HMI industri nyata.

```
┌─────────────────────────────────────────────────────────────────────┐
│ [ICSSI] ICSSI ICS Cyber Ranges        [ATTACK BANNER]    HH:MM:SS  │  ← Title Bar
├──────────────────────────────────────────────────────────────────────┤
│ File   View   Monitoring   Help                                      │  ← Menu Bar
├────────────────┬────────────────────────────────────────────────────┤
│ P&ID Diagram   │  Sensor Readings (DigitalDisplay panels)           │
│ (P-101, V-201, │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐     │
│  DP-101, dsb.) │  │  pH    │ │Flow In │ │NaOH Sp │ │NaOH Act│     │
│                │  └────────┘ └────────┘ └────────┘ └────────┘     │
├────────────────┼────────────────────────────────────────────────────┤
│ Alarm          │  Event Log                                         │
│ Annunciator    │                                                     │
├────────────────┼────────────────────────────────────────────────────┤
│ Setpoint &     │  Trend Chart (pH & NaOH)                          │
│ Control Panel  │                                                     │
└────────────────┴────────────────────────────────────────────────────┘
```

---

### Title Bar

- **ICSSI Emblem**: Badge hexagonal baja di kiri, identitas organisasi
- **Attack Detection Banner**: Menampilkan banner merah `!! ATTACK DETECTED !!` secara otomatis jika NaOH setpoint melebihi 500 ppm (threshold serangan Oldsmar)
- **Real-time Clock**: Jam digital di kanan yang update setiap detik
- **Status koneksi**: Indikator Connected/Disconnected

---

### Menu Bar

#### File
| Item | Fungsi |
|------|--------|
| Connect... | Buka dialog untuk mengganti host/port tanpa restart |
| Disconnect | Putuskan koneksi Modbus |
| Exit | Tutup aplikasi |

#### View
| Item | Fungsi |
|------|--------|
| Trend Chart | Toggle tampilkan/sembunyikan grafik trend |
| Event Log | Toggle tampilkan/sembunyikan log kejadian |
| Alarm Panel | Toggle tampilkan/sembunyikan alarm annunciator |
| Control Panel | Toggle tampilkan/sembunyikan panel setpoint |

#### Monitoring
| Item | Fungsi |
|------|--------|
| Clear Event Log | Hapus semua entri log |
| Reset Trend | Reset data historis grafik trend |
| Connection Info | Tampilkan info host, port, dan status koneksi |

#### Help
| Item | Fungsi |
|------|--------|
| About... | Dialog info aplikasi, simbol P&ID, dan legenda |

---

### P&ID Diagram

Diagram Process & Instrumentation yang menampilkan:

| Simbol | Keterangan |
|--------|-----------|
| **P-101** | Main Pump (centrifugal) — berputar saat aktif |
| **DP-101** | Dosing Pump NaOH |
| **DP-102** | Dosing Pump Chlorine |
| **V-201** | Outlet Valve (gate valve) |
| **FT-101** | Flow Transmitter In |
| **FT-201** | Flow Transmitter Out |
| **AT-101** | Analyzer Transmitter (pH/NaOH) |
| **LT-101** | Level Transmitter |

**Warna pipa:**
- Biru — air mentah/proses
- Hijau tua — air terolah
- Ungu — larutan kimia NaOH

Animasi pompa berputar saat `coil_main = ON`.

---

### Sensor Readings (DigitalDisplay)

Setiap panel menampilkan:
- Nilai numerik real-time dengan unit
- **Bar progress** berwarna: hijau (normal) → kuning (peringatan) → merah (alarm)
- Indikator alarm visual jika nilai melewati batas

| Panel | Range Normal | Alarm Hi | Alarm Lo |
|-------|-------------|----------|---------|
| pH | 6.5 – 8.5 | > 8.5 | < 6.5 |
| NaOH Aktual | 0 – 200 ppm | > 200 ppm | — |
| NaOH Setpoint | 0 – 200 ppm | > 200 ppm | — |
| Flow In | 200 – 600 L/min | — | < 200 |
| Water Level | 80 – 280 cm | > 280 | < 80 |
| Turbidity | 0 – 5 NTU | > 5 NTU | — |
| Temperature | 15 – 30 °C | — | — |
| Chlorine | 0.5 – 4 ppm | > 4 ppm | < 0.5 |
| Pressure | 20 – 70 PSI | > 70 | — |

---

### Alarm Annunciator

Panel dengan latar dark navy, menampilkan **tile alarm bercahaya (LED effect)**:

| Tile | Kondisi Aktif |
|------|--------------|
| HIGH NaOH | NaOH aktual > 200 ppm |
| PH HIGH | pH > 8.5 |
| PH LOW | pH < 6.5 |
| LOW LEVEL | Water level < 80 cm |
| FLOW FAULT | Flow in < 100 L/min |
| ESTOP ACTIVE | Emergency stop aktif |
| COMM FAULT | Koneksi Modbus terputus |
| ATTACK DETECT | NaOH setpoint > 500 ppm |

Tile alarm: merah berkedip saat aktif, abu-abu saat normal.

---

### Event Log

Log kronologis kejadian dengan kode warna:

| Warna | Level | Contoh |
|-------|-------|--------|
| Merah | ALARM | `[ALARM] NaOH setpoint anomaly: 11100 ppm` |
| Hijau | RESTORE | `[RESTORE] pH kembali ke rentang normal` |
| Kuning | WARN | `[WARN] Koneksi terputus, mencoba ulang` |
| Abu-abu | INFO | `[INFO] Connected to 127.0.0.1:502` |

---

### Trend Chart

Grafik historis 120 titik data (sekitar 2 menit) untuk:
- **pH** (garis biru)
- **NaOH Aktual** (garis oranye, skala kanan)

Garis referensi horizontal menunjukkan batas alarm.

---

### Setpoint & Control Panel

#### Setpoint NaOH
- Input field untuk mengubah setpoint NaOH (ppm)
- Tombol **Set** mengirim nilai ke OpenPLC via Modbus FC6 (write single register)
- Nilai diteruskan OpenPLC ke sensor server

#### Kontrol Aktuator
Tombol toggle untuk setiap aktuator:

| Tombol | Coil | Deskripsi |
|--------|------|-----------|
| P-101 MAIN PUMP | COIL_MAIN | Pompa utama |
| DP-101 DOSING PUMP | COIL_DOSING | Pompa dosing NaOH |
| DP-102 CHLOR PUMP | COIL_CHLOR | Pompa dosing chlorine |
| V-201 OUTLET VALVE | COIL_OUTLET | Katup outlet |

#### Emergency Stop
- Tombol **E-STOP** besar berwarna merah gelap
- Toggle aktif/nonaktif
- Saat aktif: semua pompa berhenti di level PLC, warna berubah merah terang

---

### Connect Dialog

Dapat diakses via **File → Connect...**:
- Ubah **host IP** dan **port** tanpa restart aplikasi
- SCADA otomatis reconnect ke target baru

---

## Simulasi Serangan

### Skenario: Insiden Oldsmar (8 Feb 2021)

Penyerang menggunakan TeamViewer yang dikonfigurasi lemah untuk mengakses SCADA secara remote, lalu mengubah setpoint NaOH dari 111 ppm menjadi **11,100 ppm** (100× lipat). Operator mendeteksi dan mengembalikan dalam beberapa menit.

### Cara Simulasi

```bash
# Dari komputer penyerang (arahkan ke IP OpenPLC)
python attack/oldsmar_attack.py --host 192.168.x.x

# Mode otomatis (langsung serang tanpa interaksi)
python attack/oldsmar_attack.py --mode auto --host 192.168.x.x

# Pulihkan ke kondisi normal
python attack/oldsmar_attack.py --mode restore --host 192.168.x.x
```

### Menu Serangan

| Pilihan | Aksi |
|---------|------|
| [1] Serangan Oldsmar | Set NaOH ke 11,100 ppm dengan narasi step-by-step |
| [2] Pulihkan | Kembalikan NaOH ke 111 ppm |
| [3] Aktifkan E-Stop | Matikan semua pompa |
| [4] Nonaktifkan E-Stop | Hidupkan kembali |
| [5] Set NaOH manual | Input nilai bebas |
| [6] Refresh | Update tampilan sensor |

### Dampak Serangan (terlihat di SCADA)

1. Banner **`!! ATTACK DETECTED !!`** muncul di title bar
2. Tile **ATTACK DETECT** dan **HIGH NaOH** menyala di alarm annunciator
3. Event log mencatat anomali setpoint
4. Grafik trend menunjukkan lonjakan NaOH
5. pH air naik seiring NaOH berlebih dipompa

---

## Struktur Direktori

```
icssi-digital-twin/
├── sensors/
│   ├── sensor_server.py      # Modbus TCP server + simulasi fisika
│   ├── physics.py            # Model fisika proses WWTP
│   └── config.py             # Konfigurasi register map & parameter
├── openplc/
│   ├── wwtp_control.st       # Program IEC 61131-3 Structured Text
│   └── openplc_setup.md      # Panduan konfigurasi slave device
├── scada/
│   ├── main.py               # Aplikasi SCADA HMI (tkinter)
│   ├── comms.py              # Modbus polling thread
│   ├── theme.py              # Konstanta warna & font
│   └── assets.py             # Fungsi gambar P&ID (Pillow)
├── attack/
│   └── oldsmar_attack.py     # Simulasi serangan Oldsmar
├── start_lab.bat             # Launcher Windows
└── README.md                 # Dokumentasi ini
```

---

## Referensi

- [CISA Alert AA21-042A — Oldsmar Water Treatment Facility](https://www.cisa.gov/news-events/cybersecurity-advisories/aa21-042a)
- IEC 61131-3 Structured Text Standard
- Modbus Application Protocol Specification V1.1b3

---

> **PERINGATAN:** Seluruh komponen dalam repositori ini **hanya untuk penggunaan di lingkungan lab / cyber range yang terisolasi**. Dilarang keras digunakan terhadap sistem nyata.

*ICSSI — Industrial Control System Security Indonesia*
