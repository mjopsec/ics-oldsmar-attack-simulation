"""
Konfigurasi Sensor Server - Oldsmar WWTP Digital Twin
"""

# ── Modbus TCP Server ─────────────────────────────────────────────────────────
MODBUS_HOST = "0.0.0.0"
MODBUS_PORT = 5020          # Port Modbus TCP (default 502, pakai 5020 agar tidak butuh root)

# ── Modbus Register Map ───────────────────────────────────────────────────────
# INPUT REGISTERS (OpenPLC baca sebagai %IW) – sensor membaca environment
# Alamat 0-based (pymodbus), di PLC diakses sebagai 30001+
class InputReg:
    PH              = 0   # pH × 100  (e.g., 720 = 7.20 pH)
    FLOW_IN         = 1   # Flow masuk (L/min)
    NAOH_TANK_LEVEL = 2   # Level tangki NaOH (%)
    WATER_LEVEL     = 3   # Level bak pengolahan (cm)
    TURBIDITY       = 4   # Kekeruhan NTU × 10  (e.g., 15 = 1.5 NTU)
    TEMPERATURE     = 5   # Suhu air °C × 10  (e.g., 215 = 21.5°C)
    CHLORINE        = 6   # Kadar klorin ppm × 100  (e.g., 200 = 2.00 ppm)
    PRESSURE        = 7   # Tekanan PSI × 10  (e.g., 450 = 45.0 PSI)
    NAOH_ACTUAL_PPM = 8   # Kadar NaOH aktual di air ppm × 10  (111 ppm = 1110)
    ALARM_STATUS    = 9   # Bitmask alarm (bit0=pH_hi, bit1=NaOH_hi, bit2=flow_lo, ...)
    FLOW_OUT        = 10  # Flow keluar (L/min)

# HOLDING REGISTERS (OpenPLC tulis sebagai %QW, SCADA juga bisa tulis) – setpoint
# Alamat 0-based, di PLC diakses sebagai 40001+
class HoldingReg:
    NAOH_SETPOINT   = 0   # Setpoint dosis NaOH ppm × 10  (normal 1110 = 111.0 ppm)
    CHLORINE_SP     = 1   # Setpoint klorin ppm × 100  (normal 200 = 2.00 ppm)
    FLOW_SETPOINT   = 2   # Setpoint flow (L/min)
    PUMP_SPEED      = 3   # Kecepatan pompa dosing (0-100%)

# COILS (OpenPLC tulis sebagai %QX) – kontrol aktuator
class Coil:
    MAIN_PUMP       = 0   # Pompa utama ON/OFF
    DOSING_PUMP     = 1   # Pompa dosing kimia ON/OFF
    OUTLET_VALVE    = 2   # Katup outlet BUKA/TUTUP
    EMERGENCY_STOP  = 3   # Emergency stop (1 = STOP semua)
    CHLORINE_PUMP   = 4   # Pompa klorinasi ON/OFF

# DISCRETE INPUTS (sensor digital, OpenPLC baca sebagai %IX)
class DiscreteInput:
    LEVEL_HI_HI     = 0   # Level terlalu tinggi (float switch)
    LEVEL_LO_LO     = 1   # Level terlalu rendah (float switch)
    NAOH_TANK_EMPTY = 2   # Tangki NaOH habis
    FLOW_FAULT      = 3   # Gangguan flow

# ── Nilai Normal Operasi ──────────────────────────────────────────────────────
NORMAL = {
    "ph":           720,   # 7.20 pH
    "flow_in":      520,   # 520 L/min
    "naoh_tank":    80,    # 80%
    "water_level":  210,   # 210 cm
    "turbidity":    12,    # 1.2 NTU
    "temperature":  215,   # 21.5°C
    "chlorine":     195,   # 1.95 ppm
    "pressure":     448,   # 44.8 PSI
    "naoh_actual":  1110,  # 111.0 ppm  ← nilai Oldsmar sebelum serangan
    "flow_out":     505,   # 505 L/min
}

# ── Batas Alarm ───────────────────────────────────────────────────────────────
ALARM = {
    "ph_hi":        850,   # pH > 8.50 → alarm
    "ph_lo":        620,   # pH < 6.20 → alarm
    "naoh_hi":      200,   # NaOH aktual > 200 ppm → alarm (register IR×10, threshold ×10=2000)
    "flow_lo":      200,   # Flow < 200 L/min → alarm
    "turbidity_hi": 100,   # Turbiditas > 10.0 NTU → alarm
    "pressure_hi":  600,   # Tekanan > 60.0 PSI → alarm
}

# ── Default Holding Registers (setpoint awal) ─────────────────────────────────
DEFAULT_SETPOINTS = {
    HoldingReg.NAOH_SETPOINT:  111,   # 111 ppm ← TARGET SERANGAN OLDSMAR: 11100 (11,100 ppm)
    # NaOH setpoint TIDAK di-scale (1 unit = 1 ppm), max uint16=65535 ppm
    HoldingReg.CHLORINE_SP:    200,   # 2.00 ppm (÷100)
    HoldingReg.FLOW_SETPOINT:  520,   # 520 L/min
    HoldingReg.PUMP_SPEED:     75,    # 75%
}

# ── Default Coils (status awal aktuator) ──────────────────────────────────────
DEFAULT_COILS = {
    Coil.MAIN_PUMP:      True,
    Coil.DOSING_PUMP:    True,
    Coil.OUTLET_VALVE:   True,
    Coil.EMERGENCY_STOP: False,
    Coil.CHLORINE_PUMP:  True,
}

# ── Update interval simulasi (detik) ─────────────────────────────────────────
SIM_UPDATE_INTERVAL = 1.0
