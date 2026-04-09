# OpenPLC Setup — Oldsmar WWTP Digital Twin

## Arsitektur Sistem

```
┌─────────────────────────────────────────────────────────────────┐
│                     ICSSI ICS Cyber Range                       │
│                                                                 │
│  [Sensor Server]          [OpenPLC Runtime]       [SCADA]       │
│  sensors/                 (sudah terinstall)      scada/        │
│  sensor_server.py         port: 502               main.py       │
│  port: 5020               ┌─────────────┐         port: 502     │
│                           │  ST Program │                       │
│  Modbus TCP Slave ◄───────┤  (Master)   ├────────► Modbus TCP   │
│  (field devices)          │  polls setiap│         Slave         │
│                           │  100ms      │         (HMI target)  │
│                           └─────────────┘                       │
│                                 ▲                               │
│                                 │ SCADA baca/tulis              │
│                           [Operator SCADA]                      │
└─────────────────────────────────────────────────────────────────┘

Data flow:
  Sensor Server (5020) ──► OpenPLC ──► SCADA (baca dari port 502)
  SCADA tulis setpoint ──► OpenPLC ──► Sensor Server (5020)
  Attack script        ──► OpenPLC (port 502) [realistis: via HMI]
```

---

## Langkah 1: Upload Program ST ke OpenPLC

Buka OpenPLC Runtime web interface: http://localhost:8080

Login → **Programs** → **Upload Program** → upload file `openplc/wwtp_control.st`

Atau copy-paste kode di bawah ke editor OpenPLC.

---

## Langkah 2: Konfigurasi Slave Device (OpenPLC Baca Sensor Server)

OpenPLC Runtime → **Slave Devices** → **Add new device**

### Device Settings

| Field          | Value                     |
|----------------|---------------------------|
| Device Name    | WWTP_Sensors              |
| Device Type    | Generic Modbus TCP Device |
| IP Address     | 127.0.0.1                 |
| Port           | 5020                      |
| Slave ID       | 1                         |
| Polling Period | 100 ms                    |

### Register Mapping — Form Slave Device

Isi form berikut di halaman konfigurasi slave device:

| Section | Start Address | Size | Keterangan |
|---------|:---:|:---:|---|
| Discrete Inputs (%IX100.0) | 0 | **0** | Tidak dipakai |
| Coils (%QX100.0) | **0** | **5** | Tulis aktuator ke sensor server |
| Input Registers (%IW100) | **0** | **11** | Baca semua sensor |
| Holding Registers - Read (%IW100) | 0 | **0** | **HARUS 0** — kalau > 0 akan overwrite data sensor! |
| Holding Registers - Write (%QW100) | **0** | **4** | Tulis setpoint ke sensor server |

> **Catatan addressing:** pymodbus 3.x menggunakan `zero_mode=False` secara default —
> server otomatis menambah +1 ke address yang diterima, sehingga client start=0 sudah
> mengakses register pertama (pH) dengan benar. Start Address = 0 adalah nilai yang tepat.
>
> **Penting — Holding Registers - Read harus Size=0:**
> "Holding Registers - Read" dan "Input Registers" keduanya mapping ke base %IW100.
> Jika "Holding Registers - Read" size > 0, datanya akan menimpa nilai sensor di %IW100-107.

Detail mapping `%IW0` - `%IW10`:

| %IW  | IR Addr | Nama            | Scaling        |
|------|---------|-----------------|----------------|
| %IW0 | 0       | pH              | ÷100 → pH unit |
| %IW1 | 1       | Flow In         | L/min          |
| %IW2 | 2       | NaOH Tank Level | %              |
| %IW3 | 3       | Water Level     | cm             |
| %IW4 | 4       | Turbidity       | ÷10 → NTU      |
| %IW5 | 5       | Temperature     | ÷10 → °C       |
| %IW6 | 6       | Chlorine        | ÷100 → ppm     |
| %IW7 | 7       | Pressure        | ÷10 → PSI      |
| %IW8 | 8       | NaOH Actual     | ÷10 → ppm      |
| %IW9 | 9       | Alarm Bitmask   | bit flags      |
|%IW10 | 10      | Flow Out        | L/min          |

### Register Mapping — WRITE (OpenPLC tulis kembali ke sensor server)

Klik **Add Register** untuk setiap baris:

| FC   | Start Address | Count | OpenPLC Var | Keterangan                          |
|------|---------------|-------|-------------|-------------------------------------|
| FC16 | 0             | 4     | %QW0        | Tulis setpoints ke sensor server    |
| FC15 | 0             | 5     | %QX0.0      | Tulis coils (aktuator) ke sensor    |

Detail mapping setpoints yang ditulis ke sensor server:

| %QW  | HR Addr | Nama              | Default | Satuan         |
|------|---------|-------------------|---------|----------------|
| %QW0 | 0       | NaOH Setpoint     | 111     | ppm (unscaled) |
| %QW1 | 1       | Chlorine Setpoint | 200     | ×100 ppm       |
| %QW2 | 2       | Flow Setpoint     | 520     | L/min          |
| %QW3 | 3       | Pump Speed        | 75      | %              |

Detail coils:

| %QX   | Coil Addr | Nama           | Default |
|-------|-----------|----------------|---------|
| %QX0.0 | 0        | Main Pump      | TRUE    |
| %QX0.1 | 1        | Dosing Pump    | TRUE    |
| %QX0.2 | 2        | Outlet Valve   | TRUE    |
| %QX0.3 | 3        | Emergency Stop | FALSE   |
| %QX0.4 | 4        | Chlorine Pump  | TRUE    |

---

## Langkah 3: Program Structured Text (ST)

Simpan sebagai `openplc/wwtp_control.st` dan upload ke OpenPLC:

```pascal
(* ============================================================
   ICSSI ICS Cyber Range — Oldsmar WWTP Control Logic
   Referensi: Insiden Oldsmar, Florida, 8 Feb 2021
   ============================================================ *)

PROGRAM wwtp_control
VAR
    (* === INPUT DARI SENSOR SERVER (via Modbus %IW) === *)
    pH_scaled       : INT   AT %IW0;   (* pH × 100, contoh: 720 = pH 7.20 *)
    flow_in         : INT   AT %IW1;   (* L/min *)
    naoh_tank_pct   : INT   AT %IW2;   (* % sisa NaOH di tangki *)
    water_level_cm  : INT   AT %IW3;   (* cm *)
    turbidity_x10   : INT   AT %IW4;   (* NTU × 10 *)
    temp_x10        : INT   AT %IW5;   (* °C × 10 *)
    chlorine_x100   : INT   AT %IW6;   (* ppm × 100 *)
    pressure_x10    : INT   AT %IW7;   (* PSI × 10 *)
    naoh_actual_x10 : INT   AT %IW8;   (* ppm actual × 10 *)
    alarm_bits      : INT   AT %IW9;   (* bitmask alarm *)
    flow_out        : INT   AT %IW10;  (* L/min *)

    (* === OUTPUT KE SENSOR SERVER (via Modbus %QW / %QX) === *)
    naoh_setpoint   : INT   AT %QW0;   (* NaOH SP ppm, normal=111 *)
    chlorine_sp     : INT   AT %QW1;   (* Chlorine SP ×100 *)
    flow_sp         : INT   AT %QW2;   (* Flow SP L/min *)
    pump_speed      : INT   AT %QW3;   (* Pump speed % *)

    main_pump       : BOOL  AT %QX0.0; (* TRUE = running *)
    dosing_pump     : BOOL  AT %QX0.1;
    outlet_valve    : BOOL  AT %QX0.2;
    emergency_stop  : BOOL  AT %QX0.3;
    chlorine_pump   : BOOL  AT %QX0.4;

    (* === VARIABEL INTERNAL === *)
    pH_real         : REAL;
    naoh_actual_ppm : REAL;
    alarm_naoh_hi   : BOOL;
    alarm_ph_hi     : BOOL;
    alarm_ph_lo     : BOOL;
    alarm_low_level : BOOL;
END_VAR

(* ── Konversi nilai register ke unit nyata ── *)
pH_real         := INT_TO_REAL(pH_scaled)       / 100.0;
naoh_actual_ppm := INT_TO_REAL(naoh_actual_x10) / 10.0;

(* ── Deteksi alarm ── *)
alarm_naoh_hi   := naoh_actual_ppm > 200.0;    (* NaOH > 200 ppm = BAHAYA *)
alarm_ph_hi     := pH_real > 8.5;              (* pH tinggi akibat NaOH *)
alarm_ph_lo     := pH_real < 6.5;              (* pH rendah *)
alarm_low_level := water_level_cm < 30;        (* level rendah *)

(* ── Safety Interlock ──────────────────────────────────────────
   Jika NaOH terlalu tinggi ATAU pH berbahaya: hentikan dosing,
   aktifkan E-Stop. Ini adalah interlock yang GAGAL dicek
   pada insiden Oldsmar 2021.
   ─────────────────────────────────────────────────────────── *)
IF alarm_naoh_hi OR alarm_ph_hi THEN
    dosing_pump    := FALSE;
    emergency_stop := TRUE;
END_IF;

(* ── Operasi Normal ── *)
IF NOT emergency_stop THEN
    main_pump     := TRUE;
    dosing_pump   := TRUE;
    outlet_valve  := TRUE;
    chlorine_pump := TRUE;

    (* Nilai default setpoint — akan di-override oleh SCADA jika operator mengubah *)
    IF naoh_setpoint = 0 THEN
        naoh_setpoint := 111;     (* 111 ppm — nilai normal Oldsmar *)
    END_IF;
    IF flow_sp = 0 THEN
        flow_sp := 520;
    END_IF;
    IF pump_speed = 0 THEN
        pump_speed := 75;
    END_IF;
END_IF;

END_PROGRAM
```

---

## Langkah 4: Konfigurasi SCADA (baca dari OpenPLC)

SCADA secara default membaca dari port **502** (OpenPLC Modbus TCP).

```
cd scada
python main.py --host 127.0.0.1 --port 502
```

Jika OpenPLC menggunakan port berbeda, sesuaikan `--port`.

> **Catatan port OpenPLC:**  
> Port default Modbus TCP OpenPLC adalah **502**.  
> Jika muncul error "permission denied" di Windows, coba port **5502** dan pastikan OpenPLC dikonfigurasi menggunakan port yang sama.

---

## Langkah 5: Urutan Menjalankan Lab

```
Urutan START:
  1.  python sensors/sensor_server.py          ← Field devices
  2.  OpenPLC Runtime (sudah running)           ← PLC logic
  3.  python scada/main.py --port 502          ← Operator HMI
  4.  python attack/oldsmar_attack.py --port 502  ← Serangan (dari komputer lain)

Urutan STOP:
  SCADA → Ctrl+C
  OpenPLC → Stop program via web interface
  Sensor Server → Ctrl+C
```

---

## Langkah 6: Verifikasi di OpenPLC Monitoring

OpenPLC Runtime → **Monitoring** → cari variabel:

| Variabel | Nilai Normal | Keterangan                    |
|----------|-------------|-------------------------------|
| %IW0     | ~720        | pH 7.20                       |
| %IW8     | ~1110       | NaOH actual 111.0 ppm (×10)  |
| %QW0     | 111         | NaOH setpoint 111 ppm         |
| %QX0.0   | TRUE        | Main pump running             |
| %QX0.1   | TRUE        | Dosing pump running           |
| %QX0.3   | FALSE       | E-Stop tidak aktif            |

---

## Skenario Serangan Oldsmar (dari komputer attacker)

Serangan diarahkan ke OpenPLC port 502 (bukan langsung ke sensor server),
simulasi attacker yang mengakses HMI dari luar dan mengubah setpoint:

```
python attack/oldsmar_attack.py --host <IP_OPENPLC> --port 502
```

Atau tetap ke sensor server langsung (bypass PLC — skenario field device attack):

```
python attack/oldsmar_attack.py --host <IP_SENSOR> --port 5020
```

Dampak yang terlihat di SCADA:
- NaOH Setpoint naik dari 111 → 11,100 ppm
- pH naik dari 7.2 → 9.0+ dalam 5-7 detik
- Alarm NAOH DANGER dan pH HIGH aktif (merah) di annunciator panel
- P&ID diagram menampilkan warning overlay di mix tank
