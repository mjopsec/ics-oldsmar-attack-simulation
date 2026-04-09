(* ============================================================
   ICSSI ICS Cyber Range -- Oldsmar WWTP Control Logic
   Referensi: Insiden Oldsmar, Florida, 8 Feb 2021

   Address mapping (slave device pertama, base offset 100):
     Input Registers  : %IW100-%IW110  <- sensor server IR 0-10
     Holding Reg Write: %QW100-%QW103  <- sensor server HR 0-3
     Coils Write      : %QX100.0-%QX100.4 <- sensor server Coil 0-4
   ============================================================ *)

PROGRAM wwtp_control

VAR
    (* === INPUT REGISTERS: sensor readings dari sensor server === *)
    pH_scaled       AT %IW100 : INT;
    flow_in         AT %IW101 : INT;
    naoh_tank_pct   AT %IW102 : INT;
    water_level_cm  AT %IW103 : INT;
    turbidity_x10   AT %IW104 : INT;
    temp_x10        AT %IW105 : INT;
    chlorine_x100   AT %IW106 : INT;
    pressure_x10    AT %IW107 : INT;
    naoh_actual_x10 AT %IW108 : INT;
    alarm_bits      AT %IW109 : INT;
    flow_out        AT %IW110 : INT;
    (* === HOLDING REGISTER OUTPUTS: setpoints ke sensor server === *)
    naoh_setpoint   AT %QW100 : INT;
    chlorine_sp     AT %QW101 : INT;
    flow_sp         AT %QW102 : INT;
    pump_speed      AT %QW103 : INT;
    (* === COIL OUTPUTS: kontrol aktuator ke sensor server === *)
    main_pump       AT %QX100.0 : BOOL;
    dosing_pump     AT %QX100.1 : BOOL;
    outlet_valve    AT %QX100.2 : BOOL;
    emergency_stop  AT %QX100.3 : BOOL;
    chlorine_pump   AT %QX100.4 : BOOL;
END_VAR

VAR
    pH_real         : REAL;
    naoh_actual_ppm : REAL;
    alarm_naoh_hi   : BOOL;
    alarm_ph_hi     : BOOL;
    alarm_ph_lo     : BOOL;
    alarm_low_level : BOOL;
END_VAR

pH_real         := INT_TO_REAL(pH_scaled)       / 100.0;
naoh_actual_ppm := INT_TO_REAL(naoh_actual_x10) / 10.0;

(* Alarm flags - hanya untuk monitoring SCADA, tidak auto-stop *)
(* Sama seperti sistem Oldsmar nyata: tidak ada auto-protection *)
alarm_naoh_hi   := naoh_actual_ppm > 200.0;
alarm_ph_hi     := pH_real > 8.5;
alarm_ph_lo     := pH_real < 6.5;
alarm_low_level := water_level_cm < 30;

(* Pompa berjalan terus kecuali operator aktifkan E-Stop *)
IF NOT emergency_stop THEN
    main_pump     := TRUE;
    dosing_pump   := TRUE;
    outlet_valve  := TRUE;
    chlorine_pump := TRUE;

    (* Inisialisasi setpoint jika nol (startup) *)
    IF naoh_setpoint = 0 THEN
        naoh_setpoint := 111;
    END_IF;
    IF chlorine_sp = 0 THEN
        chlorine_sp := 200;
    END_IF;
    IF flow_sp = 0 THEN
        flow_sp := 520;
    END_IF;
    IF pump_speed = 0 THEN
        pump_speed := 75;
    END_IF;
ELSE
    (* E-Stop aktif: hentikan semua pompa *)
    main_pump     := FALSE;
    dosing_pump   := FALSE;
    outlet_valve  := FALSE;
    chlorine_pump := FALSE;
END_IF;

END_PROGRAM


CONFIGURATION Config0

    RESOURCE Res0 ON PLC
        TASK TaskMain(INTERVAL := T#50ms, PRIORITY := 0);
        PROGRAM Inst0 WITH TaskMain : wwtp_control;
    END_RESOURCE

END_CONFIGURATION
