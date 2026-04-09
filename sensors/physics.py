"""
Simulasi Fisika Proses WWTP (Water Treatment Plant)
Mensimulasikan dinamika proses pengolahan air berdasarkan setpoint dan kondisi plant.

Model disederhanakan untuk keperluan lab cyber range, bukan model fisika yang presisi.
"""

import math
import random
import time
from config import NORMAL, ALARM, InputReg, HoldingReg, Coil


class WaterTreatmentPhysics:
    """
    Model fisika proses pengolahan air Oldsmar WWTP.

    State variables (nilai aktual proses):
    - ph            : pH air (scaled ×100)
    - flow_in       : Flow masuk (L/min)
    - naoh_tank     : Level tangki NaOH (%)
    - water_level   : Level bak (cm)
    - turbidity     : Kekeruhan (scaled ×10)
    - temperature   : Suhu (scaled ×10)
    - chlorine      : Kadar klorin (scaled ×100)
    - pressure      : Tekanan (scaled ×10)
    - naoh_actual   : Kadar NaOH aktual di air (scaled ×10, ppm)
    - flow_out      : Flow keluar (L/min)
    """

    def __init__(self):
        # State: semua dalam unit scaled (sama seperti register Modbus)
        self.state = dict(NORMAL)  # copy nilai normal

        # Internal process state (unscaled float)
        self._ph_real          = 7.20
        self._flow_in_real     = 520.0
        self._naoh_tank_real   = 80.0
        self._water_level_real = 210.0
        self._turbidity_real   = 1.2
        self._temperature_real = 21.5
        self._chlorine_real    = 1.95
        self._pressure_real    = 44.8
        self._naoh_actual_real = 111.0   # ← Oldsmar normal: 111 ppm
        self._flow_out_real    = 505.0

        # Noise seed
        self._t = 0.0
        self._alarm_bits = 0

    def update(self, setpoints: dict, coils: dict, dt: float = 1.0):
        """
        Update state fisika berdasarkan setpoint dan status aktuator.

        Args:
            setpoints: dict {register_addr: value} dari holding registers
            coils    : dict {coil_addr: bool}  dari coil registers
            dt       : delta waktu (detik)
        """
        self._t += dt

        naoh_sp    = float(setpoints.get(HoldingReg.NAOH_SETPOINT, 111))     # ppm (tidak di-scale)
        chlorine_sp = setpoints.get(HoldingReg.CHLORINE_SP,  200)  / 100.0  # ppm
        flow_sp    = setpoints.get(HoldingReg.FLOW_SETPOINT, 520)           # L/min
        pump_speed = setpoints.get(HoldingReg.PUMP_SPEED,    75)   / 100.0  # 0-1

        # Hanya E-Stop yang menghentikan proses — coil individu diabaikan untuk physics
        # (sama seperti sistem Oldsmar nyata: semua pompa berjalan terus, hanya operator
        #  yang bisa menghentikan lewat Emergency Stop)
        estop = coils.get(Coil.EMERGENCY_STOP, False)
        active = not estop

        # ── Flow In ───────────────────────────────────────────────────────────
        if active:
            target_flow = flow_sp * pump_speed
            self._flow_in_real += (target_flow - self._flow_in_real) * 0.1 * dt
        else:
            self._flow_in_real *= (1 - 0.3 * dt)

        self._flow_in_real = max(0, self._flow_in_real)

        # ── Flow Out ──────────────────────────────────────────────────────────
        if active:
            self._flow_out_real = self._flow_in_real * 0.97 + self._noise(5)
        else:
            self._flow_out_real *= (1 - 0.2 * dt)

        self._flow_out_real = max(0, self._flow_out_real)

        # ── Water Level ───────────────────────────────────────────────────────
        net_flow = self._flow_in_real - self._flow_out_real
        self._water_level_real += net_flow * 0.002 * dt
        self._water_level_real = max(50, min(300, self._water_level_real))

        # ── Pressure ─────────────────────────────────────────────────────────
        if active:
            target_pressure = 44.0 + (self._flow_in_real / max(flow_sp, 1)) * 6.0
        else:
            target_pressure = 0.0
        self._pressure_real += (target_pressure - self._pressure_real) * 0.15 * dt
        self._pressure_real += self._noise(0.3)

        # ── NaOH Dosing ───────────────────────────────────────────────────────
        # Physics langsung mengikuti setpoint — stabil dan realistis
        if active:
            # 8% konvergensi per detik → serangan terlihat jelas dalam ~30 detik
            lag = 0.08 * dt
            self._naoh_actual_real += (naoh_sp - self._naoh_actual_real) * lag
        else:
            # E-Stop aktif: NaOH turun perlahan (dilusi air)
            self._naoh_actual_real *= (1 - 0.02 * dt)

        self._naoh_actual_real = max(0, self._naoh_actual_real)

        # ── pH Model ─────────────────────────────────────────────────────────
        # NaOH bersifat basa: kenaikan NaOH → kenaikan pH
        # Normal: NaOH 111 ppm ≈ pH 7.2
        # Oldsmar attack: NaOH 11,100 ppm → pH bisa mencapai 13+
        naoh_ratio = self._naoh_actual_real / 111.0  # normalisasi ke nilai normal
        if naoh_ratio <= 1.0:
            target_ph = 5.5 + naoh_ratio * 1.7      # pH 5.5 (asam) → 7.2 (normal)
        elif naoh_ratio <= 10.0:
            target_ph = 7.2 + (naoh_ratio - 1) * 0.6  # 7.2 → 12.6
        else:
            target_ph = min(14.0, 7.2 + (naoh_ratio - 1) * 0.65)

        self._ph_real += (target_ph - self._ph_real) * 0.08 * dt
        self._ph_real += self._noise(0.02)
        self._ph_real = max(0, min(14, self._ph_real))

        # ── NaOH Tank Level ───────────────────────────────────────────────────
        if active:
            consumption_rate = (self._naoh_actual_real / 111.0) * 0.02
            self._naoh_tank_real -= consumption_rate * dt
        self._naoh_tank_real = max(0, min(100, self._naoh_tank_real))

        # ── Turbidity ─────────────────────────────────────────────────────────
        # Turbiditas tinggi saat flow rendah (sedimen mengendap buruk) atau pH ekstrem
        ph_stress = abs(self._ph_real - 7.2) * 0.5
        flow_stress = max(0, (400 - self._flow_in_real) / 400) * 3.0
        target_turbidity = 1.2 + ph_stress + flow_stress
        self._turbidity_real += (target_turbidity - self._turbidity_real) * 0.05 * dt
        self._turbidity_real += self._noise(0.05)
        self._turbidity_real = max(0.1, self._turbidity_real)

        # ── Temperature ───────────────────────────────────────────────────────
        # Suhu relatif stabil, dipengaruhi sedikit oleh flow
        base_temp = 21.5
        self._temperature_real += (base_temp - self._temperature_real) * 0.01 * dt
        self._temperature_real += self._noise(0.05)

        # ── Chlorine ─────────────────────────────────────────────────────────
        if active:
            self._chlorine_real += (chlorine_sp - self._chlorine_real) * 0.05 * dt
        else:
            self._chlorine_real *= (1 - 0.05 * dt)
        self._chlorine_real = max(0, self._chlorine_real)
        self._chlorine_real += self._noise(0.02)

        # ── Update Scaled State (Modbus registers) ────────────────────────────
        self.state["ph"]           = int(round(self._ph_real * 100))
        self.state["flow_in"]      = int(round(self._flow_in_real))
        self.state["naoh_tank"]    = int(round(self._naoh_tank_real))
        self.state["water_level"]  = int(round(self._water_level_real))
        self.state["turbidity"]    = int(round(self._turbidity_real * 10))
        self.state["temperature"]  = int(round(self._temperature_real * 10))
        self.state["chlorine"]     = int(round(self._chlorine_real * 100))
        self.state["pressure"]     = int(round(self._pressure_real * 10))
        self.state["naoh_actual"]  = int(round(self._naoh_actual_real * 10))
        self.state["flow_out"]     = int(round(self._flow_out_real))

        # ── Alarm Bits ────────────────────────────────────────────────────────
        bits = 0
        if self.state["ph"]        > ALARM["ph_hi"]:        bits |= (1 << 0)
        if self.state["ph"]        < ALARM["ph_lo"]:        bits |= (1 << 1)
        if self.state["naoh_actual"] > ALARM["naoh_hi"] * 10:  bits |= (1 << 2)  # naoh_actual scaled ×10
        if self.state["flow_in"]   < ALARM["flow_lo"]:      bits |= (1 << 3)
        if self.state["turbidity"] > ALARM["turbidity_hi"]: bits |= (1 << 4)
        if self.state["pressure"]  > ALARM["pressure_hi"]:  bits |= (1 << 5)
        if self._naoh_tank_real    < 10:                     bits |= (1 << 6)
        self._alarm_bits = bits
        self.state["alarm"] = bits

        return self.state.copy()

    def get_alarm_bits(self) -> int:
        return self._alarm_bits

    def get_readable_alarms(self) -> list:
        msgs = []
        b = self._alarm_bits
        if b & (1 << 0): msgs.append("pH TINGGI")
        if b & (1 << 1): msgs.append("pH RENDAH")
        if b & (1 << 2): msgs.append("NaOH BERBAHAYA")
        if b & (1 << 3): msgs.append("FLOW RENDAH")
        if b & (1 << 4): msgs.append("TURBIDITY TINGGI")
        if b & (1 << 5): msgs.append("TEKANAN TINGGI")
        if b & (1 << 6): msgs.append("TANGKI NaOH HAMPIR HABIS")
        return msgs

    def get_real_values(self) -> dict:
        """Kembalikan nilai aktual (tidak di-scale) untuk display."""
        return {
            "pH":             round(self._ph_real, 2),
            "Flow In":        round(self._flow_in_real, 1),
            "NaOH Tank":      round(self._naoh_tank_real, 1),
            "Water Level":    round(self._water_level_real, 1),
            "Turbidity":      round(self._turbidity_real, 2),
            "Temperature":    round(self._temperature_real, 1),
            "Chlorine":       round(self._chlorine_real, 2),
            "Pressure":       round(self._pressure_real, 1),
            "NaOH Actual":    round(self._naoh_actual_real, 1),
            "Flow Out":       round(self._flow_out_real, 1),
        }

    def _noise(self, amplitude: float) -> float:
        """Gaussian noise untuk simulasi sensor."""
        return random.gauss(0, amplitude * 0.3)
