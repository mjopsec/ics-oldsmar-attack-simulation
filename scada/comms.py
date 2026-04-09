"""
ICSSI SCADA - Modbus TCP Communication Thread
Polls sensor server every 1 second and forwards data to UI via queue.
"""

import threading
import queue
import time
import logging

log = logging.getLogger(__name__)

# OpenPLC base addresses (first slave device offset = 100)
# %IW100-%IW110 → Modbus IR address 100
# %QW100-%QW103 → Modbus HR address 100
# %QX100.0-%QX100.4 → Modbus coil address 800 (byte*8+bit = 100*8+0)
_IR_BASE   = 100
_HR_BASE   = 100
_COIL_BASE = 800

# Relative register offsets (used by UI)
HR_NAOH_SP   = 0   # NaOH setpoint (ppm, unscaled)
HR_CHLOR_SP  = 1   # Chlorine setpoint (×100)
HR_FLOW_SP   = 2   # Flow setpoint (L/min)
HR_PUMP_SPD  = 3   # Pump speed (%)

COIL_MAIN    = 0
COIL_DOSING  = 1
COIL_OUTLET  = 2
COIL_ESTOP   = 3
COIL_CHLOR   = 4


class ModbusPoller(threading.Thread):
    """Daemon thread: poll Modbus slave, push results to data_queue."""

    def __init__(self, host: str, port: int, data_queue: queue.Queue, cmd_queue: queue.Queue):
        super().__init__(daemon=True, name="ModbusPoller")
        self.host       = host
        self.port       = port
        self.data_queue = data_queue
        self.cmd_queue  = cmd_queue
        self._stop      = threading.Event()
        self.connected  = False
        self.client     = None

    # ── Thread entry ──────────────────────────────────────────────────────────
    def run(self):
        while not self._stop.is_set():
            if not self.connected:
                self._try_connect()
                if not self.connected:
                    self.data_queue.put({"connected": False, "error": "Cannot connect"})
                    time.sleep(3.0)
                    continue

            self._flush_commands()
            data = self._poll()
            if data:
                data["connected"] = True
                self.data_queue.put(data)
            else:
                self.connected = False
                if self.client:
                    try:
                        self.client.close()
                    except Exception:
                        pass
                self.data_queue.put({"connected": False, "error": "Poll failed"})

            time.sleep(1.0)

    # ── Connect ───────────────────────────────────────────────────────────────
    def _try_connect(self):
        try:
            from pymodbus.client import ModbusTcpClient
            if self.client:
                try:
                    self.client.close()
                except Exception:
                    pass
            self.client = ModbusTcpClient(self.host, port=self.port, timeout=3)
            self.connected = self.client.connect()
            if self.connected:
                log.info(f"Connected to Modbus server {self.host}:{self.port}")
        except Exception as e:
            log.warning(f"Connect failed: {e}")
            self.connected = False

    # ── Poll registers ────────────────────────────────────────────────────────
    def _poll(self) -> dict | None:
        try:
            ir = self.client.read_input_registers(address=_IR_BASE, count=11)
            hr = self.client.read_holding_registers(address=_HR_BASE, count=4)
            co = self.client.read_coils(address=_COIL_BASE, count=5)

            if ir.isError() or hr.isError():
                return None

            r  = ir.registers
            sp = hr.registers

            data = {
                "ph":           r[0] / 100.0,
                "flow_in":      float(r[1]),
                "naoh_tank":    float(r[2]),
                "water_level":  float(r[3]),
                "turbidity":    r[4] / 10.0,
                "temperature":  r[5] / 10.0,
                "chlorine":     r[6] / 100.0,
                "pressure":     r[7] / 10.0,
                "naoh_actual":  r[8] / 10.0,
                "alarm":        r[9],
                "flow_out":     float(r[10]),
                # setpoints
                "sp_naoh":      float(sp[0]),
                "sp_chlorine":  sp[1] / 100.0,
                "sp_flow":      float(sp[2]),
                "sp_pump_spd":  float(sp[3]),
            }

            if not co.isError():
                bits = co.bits
                data.update({
                    "coil_main":    bool(bits[0]) if len(bits) > 0 else True,
                    "coil_dosing":  bool(bits[1]) if len(bits) > 1 else True,
                    "coil_outlet":  bool(bits[2]) if len(bits) > 2 else True,
                    "coil_estop":   bool(bits[3]) if len(bits) > 3 else False,
                    "coil_chlor":   bool(bits[4]) if len(bits) > 4 else True,
                })

            return data
        except Exception as e:
            log.warning(f"Poll error: {e}")
            return None

    # ── Process write commands ────────────────────────────────────────────────
    def _flush_commands(self):
        while not self.cmd_queue.empty():
            try:
                cmd = self.cmd_queue.get_nowait()
                if cmd["type"] == "write_register":
                    self.client.write_register(address=cmd["addr"] + _HR_BASE, value=cmd["val"])
                elif cmd["type"] == "write_coil":
                    self.client.write_coil(address=cmd["addr"] + _COIL_BASE, value=cmd["val"])
            except Exception as e:
                log.warning(f"Write command error: {e}")

    # ── Public API ─────────────────────────────────────────────────────────────
    def write_register(self, addr: int, val: int):
        self.cmd_queue.put({"type": "write_register", "addr": addr, "val": val})

    def write_coil(self, addr: int, val: bool):
        self.cmd_queue.put({"type": "write_coil", "addr": addr, "val": val})

    def stop(self):
        self._stop.set()
        if self.client:
            try:
                self.client.close()
            except Exception:
                pass
