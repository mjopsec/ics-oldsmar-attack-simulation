#!/usr/bin/env python3
"""
ICSSI Digital Twin - Oldsmar WWTP Attack Simulation
===================================================
Smart Sensor Server (Modbus TCP Slave)

Menjalankan Modbus TCP Server yang:
1. Mensimulasikan sensor-sensor WWTP secara real-time
2. Meng-expose nilai sensor melalui Modbus TCP agar dibaca OpenPLC
3. Menerima setpoint/perintah dari OpenPLC atau SCADA
4. Menampilkan status live di terminal

Register Map:
  Input Registers  (30001+) → sensor readings (PLC baca)
  Holding Registers(40001+) → setpoints/control (PLC/SCADA tulis)
  Coils            (00001+) → aktuator ON/OFF  (PLC/SCADA tulis)
  Discrete Inputs  (10001+) → digital sensor   (PLC baca)

Jalankan:
  python sensor_server.py
  python sensor_server.py --host 0.0.0.0 --port 5020
"""

import asyncio
import argparse
import logging
import sys
import os
import time
import threading
from datetime import datetime

# Tambah path agar config dan physics bisa diimport
sys.path.insert(0, os.path.dirname(__file__))

from pymodbus.server import StartAsyncTcpServer
from pymodbus.datastore import (
    ModbusDeviceContext,
    ModbusServerContext,
    ModbusSequentialDataBlock,
)
from pymodbus import ModbusDeviceIdentification

from config import (
    MODBUS_HOST, MODBUS_PORT,
    InputReg, HoldingReg, Coil, DiscreteInput,
    NORMAL, DEFAULT_SETPOINTS, DEFAULT_COILS,
    SIM_UPDATE_INTERVAL,
)
from physics import WaterTreatmentPhysics

# ── Logging Setup ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# Warna terminal ANSI
class C:
    RED    = "\033[91m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    BLUE   = "\033[94m"
    CYAN   = "\033[96m"
    WHITE  = "\033[97m"
    BOLD   = "\033[1m"
    RESET  = "\033[0m"
    BG_RED = "\033[41m"

# ── Global State ───────────────────────────────────────────────────────────────
physics_engine = WaterTreatmentPhysics()
_server_context: ModbusServerContext = None
_running = True
_start_time = time.time()
_update_count = 0

# ── Datastore Init ────────────────────────────────────────────────────────────
def create_datastore() -> ModbusServerContext:
    """Buat Modbus datastore dengan nilai awal."""

    # Input Registers (fungsi 4, baca saja) – 20 register
    ir_values = [0] * 20
    ir_values[InputReg.PH]              = NORMAL["ph"]
    ir_values[InputReg.FLOW_IN]         = NORMAL["flow_in"]
    ir_values[InputReg.NAOH_TANK_LEVEL] = NORMAL["naoh_tank"]
    ir_values[InputReg.WATER_LEVEL]     = NORMAL["water_level"]
    ir_values[InputReg.TURBIDITY]       = NORMAL["turbidity"]
    ir_values[InputReg.TEMPERATURE]     = NORMAL["temperature"]
    ir_values[InputReg.CHLORINE]        = NORMAL["chlorine"]
    ir_values[InputReg.PRESSURE]        = NORMAL["pressure"]
    ir_values[InputReg.NAOH_ACTUAL_PPM] = NORMAL["naoh_actual"]
    ir_values[InputReg.ALARM_STATUS]    = 0
    ir_values[InputReg.FLOW_OUT]        = NORMAL["flow_out"]

    # Holding Registers (fungsi 3/6/16, baca-tulis) – 10 register
    hr_values = [0] * 10
    for addr, val in DEFAULT_SETPOINTS.items():
        hr_values[addr] = val

    # Coils (fungsi 1/5/15, baca-tulis) – 10 coil (int 0/1)
    co_values = [0] * 10
    for addr, val in DEFAULT_COILS.items():
        co_values[addr] = int(val)

    # Discrete Inputs (fungsi 2, baca saja) – 10 bit
    di_values = [0] * 10

    # pymodbus 3.11+: ModbusDeviceContext dengan start_address=1
    # (ctx.getValues(fc, addr=0, ...) memetakan ke block[addr+1], jadi data dimulai dari index 1)
    device = ModbusDeviceContext(
        ir=ModbusSequentialDataBlock(1, ir_values),
        hr=ModbusSequentialDataBlock(1, hr_values),
        co=ModbusSequentialDataBlock(1, co_values),
        di=ModbusSequentialDataBlock(1, di_values),
    )
    return ModbusServerContext(devices=device, single=True)


def _get_store(fc_key: str):
    """Akses datablock dari store via key: 'h'=HR, 'i'=IR, 'c'=Coil, 'd'=DI."""
    return _server_context[0x00].store[fc_key]


def _get_setpoints() -> dict:
    """Ambil setpoint dari holding registers.
    start_address=1, jadi store addr = config_addr + 1
    """
    values = _get_store("h").getValues(1, 10)
    return {i: v for i, v in enumerate(values)}


def _get_coils() -> dict:
    """Ambil status coil. start_address=1."""
    values = _get_store("c").getValues(1, 10)
    return {i: bool(v) for i, v in enumerate(values)}


def _write_input_registers(state: dict):
    """Tulis hasil simulasi fisika ke input registers (store addr = config_addr + 1)."""
    ir = _get_store("i")
    mapping = [
        (InputReg.PH,              state["ph"]),
        (InputReg.FLOW_IN,         state["flow_in"]),
        (InputReg.NAOH_TANK_LEVEL, state["naoh_tank"]),
        (InputReg.WATER_LEVEL,     state["water_level"]),
        (InputReg.TURBIDITY,       state["turbidity"]),
        (InputReg.TEMPERATURE,     state["temperature"]),
        (InputReg.CHLORINE,        state["chlorine"]),
        (InputReg.PRESSURE,        state["pressure"]),
        (InputReg.NAOH_ACTUAL_PPM, state["naoh_actual"]),
        (InputReg.ALARM_STATUS,    state["alarm"]),
        (InputReg.FLOW_OUT,        state["flow_out"]),
    ]
    for addr, val in mapping:
        ir.setValues(addr + 1, [val & 0xFFFF])  # +1 karena start_address=1


def _write_discrete_inputs(state: dict):
    """Update discrete inputs (store addr = config_addr + 1)."""
    di = _get_store("d")
    water_level = state["water_level"]
    naoh_tank   = state["naoh_tank"]
    flow_in     = state["flow_in"]

    di.setValues(DiscreteInput.LEVEL_HI_HI    + 1, [water_level > 280])
    di.setValues(DiscreteInput.LEVEL_LO_LO    + 1, [water_level < 80])
    di.setValues(DiscreteInput.NAOH_TANK_EMPTY + 1, [naoh_tank < 5])
    di.setValues(DiscreteInput.FLOW_FAULT      + 1, [flow_in < 100])


# ── Simulation Loop ────────────────────────────────────────────────────────────
def simulation_loop():
    """Thread terpisah: update fisika dan Modbus registers setiap detik."""
    global _update_count
    while _running:
        if _server_context is not None:
            setpoints = _get_setpoints()
            coils     = _get_coils()

            state = physics_engine.update(setpoints, coils, dt=SIM_UPDATE_INTERVAL)

            _write_input_registers(state)
            _write_discrete_inputs(state)

            _update_count += 1

            # Print status ke terminal
            _print_status(state, setpoints, coils)

        time.sleep(SIM_UPDATE_INTERVAL)


def _print_status(state: dict, setpoints: dict, coils: dict):
    """Tampilkan dashboard status di terminal."""
    os.system("cls" if os.name == "nt" else "clear")

    real = physics_engine.get_real_values()
    alarms = physics_engine.get_readable_alarms()
    uptime = int(time.time() - _start_time)
    naoh_sp = setpoints.get(HoldingReg.NAOH_SETPOINT, 111)  # langsung ppm

    # Deteksi kondisi serangan
    is_attack = naoh_sp > 500  # > 500 ppm sudah dianggap anomali

    print(f"{C.BOLD}{C.CYAN}{'='*65}{C.RESET}")
    print(f"{C.BOLD}{C.CYAN}  ICSSI DIGITAL TWIN - Oldsmar WWTP Sensor Server{C.RESET}")
    print(f"{C.BOLD}{C.CYAN}  Modbus TCP  |  Host: {MODBUS_HOST}  Port: {MODBUS_PORT}{C.RESET}")
    print(f"{C.BOLD}{C.CYAN}{'='*65}{C.RESET}")
    print(f"  Uptime: {uptime}s    Tick: #{_update_count}    {datetime.now().strftime('%H:%M:%S')}")
    print()

    # Status attack
    if is_attack:
        print(f"{C.BG_RED}{C.WHITE}{C.BOLD}  !! SERANGAN TERDETEKSI: NaOH SETPOINT = {naoh_sp:.1f} ppm !!  {C.RESET}")
        print()

    # Sensor readings
    ph_color = C.RED if (state["ph"] > 850 or state["ph"] < 620) else C.GREEN
    naoh_color = C.RED if state["naoh_actual"] > 2000 else C.GREEN
    flow_color = C.RED if state["flow_in"] < 200 else C.GREEN

    print(f"{C.BOLD}  SENSOR READINGS{C.RESET}")
    print(f"  {'Parameter':<22} {'Nilai':<12} {'Scaled(Modbus)':<16} {'Status'}")
    print(f"  {'-'*60}")

    rows = [
        ("pH",              f"{real['pH']:.2f}",           state['ph'],        ph_color),
        ("NaOH Aktual",     f"{real['NaOH Actual']:.1f} ppm", state['naoh_actual'], naoh_color),
        ("Flow In",         f"{real['Flow In']:.0f} L/min",  state['flow_in'],   flow_color),
        ("Flow Out",        f"{real['Flow Out']:.0f} L/min",  state['flow_out'],  C.GREEN),
        ("Water Level",     f"{real['Water Level']:.0f} cm",  state['water_level'], C.GREEN),
        ("NaOH Tank",       f"{real['NaOH Tank']:.1f} %",    state['naoh_tank'],  C.YELLOW if state['naoh_tank'] < 20 else C.GREEN),
        ("Turbidity",       f"{real['Turbidity']:.2f} NTU",  state['turbidity'],  C.GREEN),
        ("Temperature",     f"{real['Temperature']:.1f} °C", state['temperature'], C.GREEN),
        ("Chlorine",        f"{real['Chlorine']:.2f} ppm",   state['chlorine'],   C.GREEN),
        ("Pressure",        f"{real['Pressure']:.1f} PSI",   state['pressure'],   C.GREEN),
    ]

    for name, disp, scaled, color in rows:
        ok = "OK" if color == C.GREEN else ("WARN" if color == C.YELLOW else "ALARM")
        status_c = C.GREEN if ok == "OK" else (C.YELLOW if ok == "WARN" else C.RED)
        print(f"  {name:<22} {color}{disp:<12}{C.RESET} {scaled:<16} {status_c}{ok}{C.RESET}")

    print()
    print(f"{C.BOLD}  SETPOINTS (dari PLC/SCADA){C.RESET}")
    sp_naoh_color = C.RED if is_attack else C.GREEN
    print(f"  NaOH Setpoint : {sp_naoh_color}{C.BOLD}{naoh_sp:.1f} ppm{C.RESET}")
    print(f"  Chlorine SP   : {setpoints.get(HoldingReg.CHLORINE_SP, 200) / 100.0:.2f} ppm")
    print(f"  Flow SP       : {setpoints.get(HoldingReg.FLOW_SETPOINT, 520)} L/min")
    print(f"  Pump Speed    : {setpoints.get(HoldingReg.PUMP_SPEED, 75)}%")

    print()
    print(f"{C.BOLD}  STATUS AKTUATOR{C.RESET}")
    _fmt_coil = lambda v: f"{C.GREEN}ON {C.RESET}" if v else f"{C.RED}OFF{C.RESET}"
    print(f"  Main Pump      : {_fmt_coil(coils.get(Coil.MAIN_PUMP, True))}"
          f"   Dosing Pump  : {_fmt_coil(coils.get(Coil.DOSING_PUMP, True))}")
    print(f"  Outlet Valve   : {_fmt_coil(coils.get(Coil.OUTLET_VALVE, True))}"
          f"   Chlorine Pump: {_fmt_coil(coils.get(Coil.CHLORINE_PUMP, True))}")
    estop = coils.get(Coil.EMERGENCY_STOP, False)
    estop_str = f"{C.BG_RED}{C.WHITE} E-STOP ACTIVE {C.RESET}" if estop else f"{C.GREEN}Normal{C.RESET}"
    print(f"  Emergency Stop : {estop_str}")

    if alarms:
        print()
        print(f"{C.BG_RED}{C.WHITE}{C.BOLD}  ACTIVE ALARMS:{C.RESET}")
        for a in alarms:
            print(f"  {C.RED}[!] {a}{C.RESET}")

    print(f"\n{C.CYAN}  Tekan Ctrl+C untuk stop{C.RESET}")


# ── Modbus Server Identity ─────────────────────────────────────────────────────
def create_identity() -> ModbusDeviceIdentification:
    identity = ModbusDeviceIdentification()
    identity.VendorName        = "ICSSI Lab"
    identity.ProductCode       = "WWTP-DT-001"
    identity.VendorUrl         = "https://icssi.id"
    identity.ProductName       = "Oldsmar WWTP Digital Twin"
    identity.ModelName         = "Smart Sensor Server"
    identity.MajorMinorRevision = "1.0"
    return identity


# ── Main ───────────────────────────────────────────────────────────────────────
async def run_server(host: str, port: int):
    global _server_context

    _server_context = create_datastore()
    identity = create_identity()

    # Mulai simulation thread
    sim_thread = threading.Thread(target=simulation_loop, daemon=True)
    sim_thread.start()

    print(f"\n{C.GREEN}{C.BOLD}[+] Sensor Server dimulai{C.RESET}")
    print(f"    Modbus TCP -> {host}:{port}")
    print(f"    OpenPLC: tambahkan Modbus slave ke {host}:{port}")
    print(f"    Menunggu koneksi...\n")

    await StartAsyncTcpServer(
        context=_server_context,
        identity=identity,
        address=(host, port),
    )


def main():
    global _running

    parser = argparse.ArgumentParser(description="WWTP Sensor Server (Modbus TCP)")
    parser.add_argument("--host", default=MODBUS_HOST, help="Bind host")
    parser.add_argument("--port", type=int, default=MODBUS_PORT, help="Modbus TCP port")
    args = parser.parse_args()

    try:
        asyncio.run(run_server(args.host, args.port))
    except KeyboardInterrupt:
        _running = False
        print(f"\n{C.YELLOW}[!] Server dihentikan{C.RESET}")


if __name__ == "__main__":
    main()
