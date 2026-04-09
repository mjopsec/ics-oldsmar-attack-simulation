@echo off
setlocal enabledelayedexpansion
title ICSSI Digital Twin - Build EXE

echo.
echo  ============================================================
echo  ICSSI ICS Cyber Ranges - Build EXE
echo  Oldsmar WWTP Digital Twin
echo  ============================================================
echo.
echo  Pilih yang ingin di-build:
echo    1. Sensor Server (console)
echo    2. SCADA Desktop (GUI)
echo    3. Keduanya
echo    4. Keluar
echo.
set /p choice="  Pilihan [1-4]: "

if "%choice%"=="4" goto :end
if "%choice%"=="" goto :end

:: ── Install PyInstaller ─────────────────────────────────────────────────────
echo.
echo  [*] Memastikan PyInstaller tersedia...
pip install pyinstaller --quiet
if errorlevel 1 (
    echo  [!] Gagal install PyInstaller. Pastikan pip tersedia.
    pause & exit /b 1
)

:: ── Build Sensor Server ─────────────────────────────────────────────────────
if "%choice%"=="1" goto :build_sensor
if "%choice%"=="3" goto :build_sensor
goto :build_scada

:build_sensor
echo.
echo  ============================================================
echo  [*] Building Sensor Server...
echo  ============================================================
echo.

pyinstaller ^
  --onefile ^
  --console ^
  --name "ICSSI_SensorServer" ^
  --distpath "dist" ^
  --workpath "build/sensor" ^
  --hidden-import "pymodbus.framer.socket_framer" ^
  --hidden-import "pymodbus.framer.rtu_framer" ^
  --hidden-import "pymodbus.server.async_io" ^
  --hidden-import "pymodbus.datastore.context" ^
  --hidden-import "pymodbus.datastore.store" ^
  --hidden-import "asyncio" ^
  --add-data "sensors/config.py;." ^
  --add-data "sensors/physics.py;." ^
  sensors/sensor_server.py

if errorlevel 1 (
    echo.
    echo  [!] BUILD SENSOR SERVER GAGAL
    echo  [!] Periksa output di atas
    if "%choice%"=="3" goto :build_scada
    pause & exit /b 1
)
echo.
echo  [+] Sensor Server berhasil: dist\ICSSI_SensorServer.exe

if "%choice%"=="1" goto :done

:: ── Build SCADA ─────────────────────────────────────────────────────────────
:build_scada
echo.
echo  ============================================================
echo  [*] Building SCADA Desktop...
echo  ============================================================
echo.

pyinstaller ^
  --onefile ^
  --windowed ^
  --name "ICSSI_SCADA" ^
  --distpath "dist" ^
  --workpath "build/scada" ^
  --hidden-import "pymodbus.client.tcp" ^
  --hidden-import "pymodbus.framer.socket_framer" ^
  --hidden-import "tkinter" ^
  --hidden-import "tkinter.ttk" ^
  --hidden-import "PIL._tkinter_finder" ^
  --add-data "scada/theme.py;." ^
  --add-data "scada/assets.py;." ^
  --add-data "scada/comms.py;." ^
  scada/main.py

if errorlevel 1 (
    echo.
    echo  [!] BUILD SCADA GAGAL
    echo  [!] Periksa output di atas
    pause & exit /b 1
)
echo.
echo  [+] SCADA Desktop berhasil: dist\ICSSI_SCADA.exe

:done
echo.
echo  ============================================================
echo  HASIL BUILD:
if exist dist\ICSSI_SensorServer.exe (
    echo    [+] dist\ICSSI_SensorServer.exe
)
if exist dist\ICSSI_SCADA.exe (
    echo    [+] dist\ICSSI_SCADA.exe
)
echo  ============================================================
echo.
echo  CATATAN:
echo    - Sensor Server harus dijalankan SEBELUM SCADA
echo    - Sensor Server: klik 2x atau jalankan di Command Prompt
echo    - SCADA: klik 2x untuk membuka GUI
echo    - Keduanya butuh koneksi ke OpenPLC di port 502
echo.

:end
pause
