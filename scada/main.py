#!/usr/bin/env python3
"""
ICSSI ICS Cyber Ranges
Oldsmar WWTP SCADA Desktop v3.0

Industrial Control System Security Indonesia
Tampilan retro-enterprise (Wonderware/Citect/iFIX style) dengan
menu bar, about dialog, P&ID diagram, digital readout, alarm annunciator.

Jalankan: python main.py [--host 127.0.0.1] [--port 502]
Build    : pyinstaller --onefile --windowed --name ICSSI_SCADA main.py
"""

import tkinter as tk
import tkinter.ttk as ttk
from tkinter import simpledialog
import queue
import time
import argparse
import sys
import os
from collections import deque
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageTk

_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)

import theme as T
import assets as A
from comms import (
    ModbusPoller,
    HR_NAOH_SP, HR_CHLOR_SP, HR_FLOW_SP, HR_PUMP_SPD,
    COIL_MAIN, COIL_DOSING, COIL_OUTLET, COIL_ESTOP, COIL_CHLOR,
)

APP_NAME    = "ICSSI ICS Cyber Ranges"
APP_FULL    = "Industrial Control System Security Indonesia"
APP_PLANT   = "Oldsmar Water Treatment Plant — Digital Twin"
APP_VERSION = "v3.0"
APP_MODBUS  = "Modbus TCP"


# ── Utility helpers ───────────────────────────────────────────────────────────
def bevel_frame(parent, raised=True, **kw):
    kw.setdefault("bg", T.BG_MAIN)
    f = tk.Frame(parent, **kw)
    f.config(relief="raised" if raised else "sunken", bd=2)
    return f


def section_header(parent, title: str, subtitle: str = "", **kw):
    """Navy-blue section header strip with optional subtitle."""
    bg = kw.pop("bg", T.BG_DARK)
    frm = tk.Frame(parent, bg=bg)
    frm.pack(fill="x")
    left = tk.Frame(frm, bg=bg)
    left.pack(side="left", fill="y")
    # Colored accent tab on far left
    tk.Frame(left, bg=T.BG_ACCENT, width=4).pack(side="left", fill="y")
    tk.Label(left, text=f"  {title}", bg=bg, fg=T.TEXT_WHITE,
             font=T.FONT_SMALL_B, anchor="w").pack(side="left", padx=2, pady=3)
    if subtitle:
        tk.Label(frm, text=f"{subtitle}  ", bg=bg, fg="#AABBCC",
                 font=T.FONT_PID, anchor="e").pack(side="right", padx=4)
    return frm


# ══════════════════════════════════════════════════════════════════════════════
#  AboutDialog
# ══════════════════════════════════════════════════════════════════════════════
class AboutDialog(tk.Toplevel):
    """Professional about dialog with ICSSI emblem."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("About — ICSSI SCADA")
        self.resizable(False, False)
        self.configure(bg=T.BG_MAIN)
        self.grab_set()

        # ── Top band ─────────────────────────────────────────────────────
        top = tk.Frame(self, bg=T.BG_TOPBAR)
        top.pack(fill="x")

        # Emblem
        emblem_img = A.make_icssi_emblem(72)
        photo = ImageTk.PhotoImage(emblem_img)
        lbl_logo = tk.Label(top, image=photo, bg=T.BG_TOPBAR)
        lbl_logo.image = photo
        lbl_logo.pack(side="left", padx=16, pady=12)

        info = tk.Frame(top, bg=T.BG_TOPBAR)
        info.pack(side="left", fill="y", pady=10)
        tk.Label(info, text=APP_NAME, bg=T.BG_TOPBAR,
                 fg="#FFFFFF", font=("Arial", 14, "bold")).pack(anchor="w")
        tk.Label(info, text=APP_FULL, bg=T.BG_TOPBAR,
                 fg=T.TEXT_TOPBAR, font=("Arial", 10)).pack(anchor="w")
        tk.Label(info, text=f"SCADA Desktop  {APP_VERSION}",
                 bg=T.BG_TOPBAR, fg="#A9CCE3",
                 font=("Arial", 9)).pack(anchor="w", pady=(4, 0))

        # ── Info grid ────────────────────────────────────────────────────
        body = tk.Frame(self, bg=T.BG_MAIN, padx=20, pady=12)
        body.pack(fill="both")

        rows = [
            ("Simulasi",      APP_PLANT),
            ("Protokol",      "Modbus TCP (IEC 61131-3 / IEC 62443)"),
            ("Referensi",     "Insiden Oldsmar, Florida — 8 Feb 2021"),
            ("Platform",      "Python 3  ·  tkinter  ·  pymodbus  ·  Pillow"),
            ("Arsitektur",    "Sensor Server → OpenPLC → SCADA (HMI)"),
            ("Lab",           "ICSSI ICS Cyber Ranges  —  ICS/SCADA Security"),
        ]
        for i, (lbl, val) in enumerate(rows):
            bg = T.BG_PANEL if i % 2 == 0 else T.BG_MAIN
            row = tk.Frame(body, bg=bg)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=f"  {lbl}", bg=bg, fg=T.BG_DARK,
                     font=T.FONT_SMALL_B, width=14, anchor="w").pack(side="left",
                                                                      padx=(0, 8), pady=3)
            tk.Label(row, text=val, bg=bg, fg=T.TEXT_DARK,
                     font=T.FONT_SMALL, anchor="w").pack(side="left")

        # ── Legend: P&ID symbol symbols ───────────────────────────────────
        leg_frame = bevel_frame(body, raised=False)
        leg_frame.pack(fill="x", pady=(10, 4))
        section_header(leg_frame, "SIMBOL P&ID  —  ISA 5.1 / ISA 101 Standard",
                       bg=T.BG_DARK)

        sym_area = tk.Frame(leg_frame, bg=T.BG_PANEL)
        sym_area.pack(fill="x", padx=6, pady=6)

        symbols = [
            ("pump",        {"size": 44, "running": True},    "Centrifugal Pump\n(P-xxx)"),
            ("dosing_pump", {"size": 40, "running": True},    "Dosing Pump\n(DP-xxx)"),
            ("valve",       {"size": 36, "open_pct": 100},    "Gate Valve\n(V-xxx)"),
            ("flowmeter",   {"size": 36},                     "Flow Transmitter\n(FT-xxx)"),
            ("ph_sensor",   {"size": 36},                     "Analyzer\n(AT-xxx / pH)"),
            ("level_sensor",{"size": 36},                     "Level Transmitter\n(LT-xxx)"),
            ("chem_tank",   {"w": 40, "h": 56, "level_pct": 70, "label": "NaOH"},
                            "Chemical Tank\n(TK-xxx)"),
            ("filter",      {"w": 44, "h": 60},               "Sand Filter\n(F-xxx)"),
        ]
        self._sym_imgs = []
        for col, (key, kw, desc) in enumerate(symbols):
            cell = tk.Frame(sym_area, bg=T.BG_PANEL, padx=6, pady=4)
            cell.grid(row=0, column=col, padx=4, pady=4, sticky="n")
            pil_img = getattr(A, f"make_{key}")(**kw)
            bg_rgb = tuple(int(T.BG_PANEL.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
            bg_img = Image.new("RGBA", pil_img.size, (*bg_rgb, 255))
            combined = Image.alpha_composite(bg_img, pil_img).convert("RGB")
            photo = ImageTk.PhotoImage(combined)
            self._sym_imgs.append(photo)
            tk.Label(cell, image=photo, bg=T.BG_PANEL).pack()
            tk.Label(cell, text=desc, bg=T.BG_PANEL, fg=T.TEXT_MED,
                     font=("Arial", 7), justify="center").pack()

        # ── Pipe legend ───────────────────────────────────────────────────
        pipe_row = tk.Frame(leg_frame, bg=T.BG_PANEL, padx=8, pady=4)
        pipe_row.pack(fill="x", padx=6, pady=(0, 6))
        pipes = [
            (T.PIPE_WATER,   "Raw Water Line"),
            (T.PIPE_TREATED, "Treated Water Line"),
            (T.PIPE_CHEM,    "Chemical (NaOH) Line"),
        ]
        for col, (color, label) in enumerate(pipes):
            f = tk.Frame(pipe_row, bg=T.BG_PANEL)
            f.grid(row=0, column=col, padx=12)
            cv = tk.Canvas(f, width=50, height=14, bg=T.BG_PANEL,
                           bd=0, highlightthickness=0)
            cv.pack(side="left")
            cv.create_line(0, 7, 50, 7, fill=color, width=4, capstyle="round")
            tk.Label(f, text=label, bg=T.BG_PANEL, fg=T.TEXT_DARK,
                     font=T.FONT_PID).pack(side="left", padx=4)

        # ── Footer ────────────────────────────────────────────────────────
        tk.Frame(self, bg=T.BEVEL_DARK, height=1).pack(fill="x")
        foot = tk.Frame(self, bg=T.BG_PANEL, padx=12, pady=6)
        foot.pack(fill="x")
        tk.Label(foot, text="© ICSSI — Industrial Control System Security Indonesia  |  "
                 "Educational / Research Use Only",
                 bg=T.BG_PANEL, fg=T.TEXT_LIGHT, font=T.FONT_PID).pack(side="left")
        tk.Button(foot, text="  OK  ", font=T.FONT_SMALL_B,
                  bg=T.BG_DARK, fg=T.TEXT_WHITE, relief="raised", bd=2,
                  activebackground=T.BG_ACCENT, activeforeground=T.TEXT_WHITE,
                  cursor="hand2", command=self.destroy).pack(side="right")

        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        px = parent.winfo_rootx() + (parent.winfo_width()  - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.geometry(f"+{px}+{py}")


# ══════════════════════════════════════════════════════════════════════════════
#  ConnectDialog
# ══════════════════════════════════════════════════════════════════════════════
class ConnectDialog(tk.Toplevel):
    """Host / port connection dialog."""

    def __init__(self, parent, current_host: str, current_port: int):
        super().__init__(parent)
        self.title("Connect to PLC / Sensor Server")
        self.resizable(False, False)
        self.configure(bg=T.BG_MAIN)
        self.grab_set()
        self.result = None

        top = tk.Frame(self, bg=T.BG_TOPBAR, padx=12, pady=8)
        top.pack(fill="x")
        tk.Label(top, text="  Connect — Modbus TCP",
                 bg=T.BG_TOPBAR, fg=T.TEXT_WHITE, font=T.FONT_LABEL_B).pack(side="left")

        body = tk.Frame(self, bg=T.BG_MAIN, padx=20, pady=14)
        body.pack(fill="both")

        for row, (label, default, attr) in enumerate([
            ("Host / IP Address:", current_host, "_host_var"),
            ("Port:",             str(current_port), "_port_var"),
        ]):
            tk.Label(body, text=label, bg=T.BG_MAIN, fg=T.TEXT_DARK,
                     font=T.FONT_SMALL_B, width=20, anchor="w").grid(
                row=row, column=0, padx=4, pady=5, sticky="w")
            var = tk.StringVar(value=default)
            setattr(self, attr, var)
            tk.Entry(body, textvariable=var, bg=T.DISP_BG, fg=T.DISP_TEXT,
                     font=T.FONT_VALUE, width=18, relief="sunken", bd=2).grid(
                row=row, column=1, padx=4, pady=5)

        hint = ("Port 502 = OpenPLC (standard Modbus TCP)\n"
                "Port 5020 = Sensor Server (direct)")
        tk.Label(body, text=hint, bg=T.BG_MAIN, fg=T.TEXT_LIGHT,
                 font=T.FONT_PID, justify="left").grid(
            row=2, column=0, columnspan=2, padx=4, pady=(0, 4), sticky="w")

        tk.Frame(self, bg=T.BEVEL_DARK, height=1).pack(fill="x")
        btn_row = tk.Frame(self, bg=T.BG_PANEL, padx=12, pady=6)
        btn_row.pack(fill="x")
        tk.Button(btn_row, text=" Cancel ", font=T.FONT_SMALL,
                  bg=T.BG_MAIN, fg=T.TEXT_DARK, relief="raised", bd=2,
                  cursor="hand2", command=self.destroy).pack(side="right", padx=4)
        tk.Button(btn_row, text=" Connect ", font=T.FONT_SMALL_B,
                  bg=T.BG_DARK, fg=T.TEXT_WHITE, relief="raised", bd=2,
                  activebackground=T.BG_ACCENT,
                  cursor="hand2", command=self._ok).pack(side="right", padx=4)

        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        px = parent.winfo_rootx() + (parent.winfo_width()  - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.geometry(f"+{px}+{py}")

    def _ok(self):
        try:
            host = self._host_var.get().strip()
            port = int(self._port_var.get().strip())
            self.result = (host, port)
            self.destroy()
        except ValueError:
            pass


# ══════════════════════════════════════════════════════════════════════════════
#  PIDCanvas — P&ID process flow diagram
# ══════════════════════════════════════════════════════════════════════════════
class PIDCanvas(tk.Canvas):
    W, H = 920, 325

    PIPE_Y       = 138
    PIPE_W       = 5

    P101_CX      = 88
    FT101_CX     = 162
    TANK_L       = 208
    TANK_R       = 372
    TANK_T       = 62
    TANK_B       = 212

    PH_CX        = 288
    FT102_CX     = 415
    FILT_L       = 452
    FILT_R       = 518
    CL_CX        = 578
    P102_CX      = 664
    FT103_CX     = 736

    NAOH_TANK_CX = 292
    NAOH_TANK_T  = 238
    DP_CY        = 194

    def __init__(self, parent, **kw):
        super().__init__(
            parent, width=self.W, height=self.H,
            bg=T.BG_PANEL, bd=0, highlightthickness=0, **kw
        )
        self._images = {}
        self._data   = {}
        self._blink  = False
        self._draw_static_background()
        self._place_equipment()
        self._draw_pipe_labels()
        self._draw_tag_labels()

    def _draw_static_background(self):
        c = self
        c.create_rectangle(0, 0, self.W, self.H, fill=T.BG_PANEL, outline="")

        # Subtle grid dots
        for x in range(0, self.W, 32):
            for y in range(0, self.H, 32):
                c.create_oval(x-1, y-1, x+1, y+1, fill=T.BEVEL_DARK, outline="")

        PY = self.PIPE_Y

        # ── Water pipes (raw) ──────────────────────────────────────────────
        self._pipe(0,                      PY, self.P101_CX-28,     PY, "water")
        self._pipe(self.P101_CX+28,        PY, self.FT101_CX-14,    PY, "water")
        self._pipe(self.FT101_CX+14,       PY, self.TANK_L,         PY, "water")
        self._pipe(self.TANK_R,            PY, self.FT102_CX-14,    PY, "water")
        self._pipe(self.FT102_CX+14,       PY, self.FILT_L,         PY, "water")

        # ── Treated water pipes ────────────────────────────────────────────
        self._pipe(self.FILT_R,            PY, self.CL_CX-10,       PY, "treated")
        self._pipe(self.CL_CX+10,          PY, self.P102_CX-28,     PY, "treated")
        self._pipe(self.P102_CX+28,        PY, self.FT103_CX-14,    PY, "treated")
        self._pipe(self.FT103_CX+14,       PY, self.W,              PY, "treated")

        # ── NaOH chemical feed (vertical loop) ────────────────────────────
        NT_CX = self.NAOH_TANK_CX
        self._pipe(NT_CX, self.NAOH_TANK_T-4, NT_CX, self.DP_CY+22, "chem", w=3)
        self._pipe(NT_CX, self.DP_CY-22,      NT_CX, self.TANK_B,   "chem", w=3)
        # Horizontal injection tee
        self._pipe(NT_CX-32, self.TANK_B-16, NT_CX+32, self.TANK_B-16, "chem", w=3)

        # ── Chlorine dosing vertical ───────────────────────────────────────
        self._pipe(self.CL_CX, 42+52, self.CL_CX, PY, "treated", w=3)

        # ── Flow arrows ────────────────────────────────────────────────────
        self._arrow(14,          PY, "right", "water")
        self._arrow(self.W - 16, PY, "right", "treated")

        # ── Edge labels ────────────────────────────────────────────────────
        c.create_text(6, PY-16, text="RAW\nINTAKE", fill=T.TEXT_MED,
                      font=T.FONT_PID, anchor="w", justify="center")
        c.create_text(self.W-6, PY-16, text="TREATED\nOUTLET", fill=T.TEXT_MED,
                      font=T.FONT_PID, anchor="e", justify="center")

    def _pipe(self, x0, y0, x1, y1, scheme="water", w=None):
        ww = w or self.PIPE_W
        colors = {
            "water":   (T.PIPE_WATER,   T.PIPE_FILL),
            "treated": (T.PIPE_TREATED, "#6CBF8A"),
            "chem":    (T.PIPE_CHEM,    "#B48EC0"),
        }
        main_c, hi_c = colors.get(scheme, (T.PIPE_WATER, T.PIPE_FILL))
        self.create_line(x0, y0+1, x1, y1+1, fill=T.BEVEL_DARKER, width=ww+2, capstyle="round")
        self.create_line(x0, y0,   x1, y1,   fill=main_c,          width=ww,   capstyle="round")
        if abs(y1-y0) < 5:
            self.create_line(x0, y0-1, x1, y1-1, fill=hi_c, width=max(1, ww//3), capstyle="round")
        else:
            self.create_line(x0-1, y0, x1-1, y1, fill=hi_c, width=max(1, ww//3), capstyle="round")

    def _arrow(self, cx, cy, direction, scheme="water"):
        colors = {"water": T.PIPE_WATER, "treated": T.PIPE_TREATED, "chem": T.PIPE_CHEM}
        c = colors.get(scheme, T.PIPE_WATER)
        s = 8
        if direction == "right":
            pts = [(cx-s, cy-s//2), (cx+s//2, cy), (cx-s, cy+s//2)]
        else:
            pts = [(cx+s, cy-s//2), (cx-s//2, cy), (cx+s, cy+s//2)]
        self.create_polygon(pts, fill=c, outline=T.BEVEL_DARKER)

    def _place_equipment(self):
        PY = self.PIPE_Y

        self._place_pil(A.make_valve(36, open_pct=100),     32,   PY,  "valve_inlet")
        self._place_pil(A.make_pump(56, running=True),  self.P101_CX, PY,  "pump_p101")
        self._place_pil(A.make_flowmeter(32),           self.FT101_CX, PY, "ft101")

        tw = self.TANK_R - self.TANK_L
        th = self.TANK_B - self.TANK_T
        self._place_pil(A.make_tank(tw, th, 75, color_scheme="water"),
                        (self.TANK_L+self.TANK_R)//2, (self.TANK_T+self.TANK_B)//2,
                        "tank_mix", anchor_tl=True, x0=self.TANK_L, y0=self.TANK_T)

        self._place_pil(A.make_ph_sensor(32), self.PH_CX, PY-20, "ph_sensor")
        self.create_line(self.PH_CX, PY-4, self.PH_CX, PY,
                         fill=T.BEVEL_DARK, width=1, dash=(3, 3))

        self._place_pil(A.make_chemical_tank(54, 68, 80, "NaOH"),
                        self.NAOH_TANK_CX, self.NAOH_TANK_T+34,
                        "tank_naoh", anchor_tl=True,
                        x0=self.NAOH_TANK_CX-27, y0=self.NAOH_TANK_T)

        self._place_pil(A.make_dosing_pump(44, running=True),
                        self.NAOH_TANK_CX, self.DP_CY, "pump_dp101")
        self._place_pil(A.make_valve(30, open_pct=100),
                        self.NAOH_TANK_CX, self.TANK_B-15, "valve_naoh")

        self._place_pil(A.make_flowmeter(32),   self.FT102_CX, PY, "ft102")
        self._place_pil(A.make_filter_unit(62, 84),
                        (self.FILT_L+self.FILT_R)//2,
                        (self.TANK_T+self.TANK_B)//2,
                        "filter_f101", anchor_tl=True,
                        x0=self.FILT_L, y0=self.TANK_T+2)

        self._place_pil(A.make_chemical_tank(40, 52, 65, "Cl\u2082"),
                        self.CL_CX, 64, "tank_cl",
                        anchor_tl=True, x0=self.CL_CX-20, y0=14)
        self._place_pil(A.make_dosing_pump(36, running=True),
                        self.CL_CX, 96, "pump_dp102")

        self._place_pil(A.make_pump(56, running=True),  self.P102_CX, PY, "pump_p102")
        self._place_pil(A.make_flowmeter(32),           self.FT103_CX, PY, "ft103")

        lx = self.TANK_L - 18
        self._place_pil(A.make_level_sensor(28), lx, PY-10, "lt101")
        self.create_line(lx+14, PY-10, self.TANK_L+1, PY-10,
                         fill=T.BEVEL_DARK, width=1, dash=(2, 3))

    def _place_pil(self, img: Image.Image, cx, cy, tag, anchor_tl=False, x0=None, y0=None):
        bg_rgb = tuple(int(T.BG_PANEL.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
        bg = Image.new("RGBA", img.size, (*bg_rgb, 255))
        photo = ImageTk.PhotoImage(Image.alpha_composite(bg, img).convert("RGB"))
        self._images[tag] = photo
        if anchor_tl:
            self.create_image(x0, y0, anchor="nw", image=photo, tags=tag)
        else:
            self.create_image(cx, cy, anchor="center", image=photo, tags=tag)

    def _draw_pipe_labels(self):
        PY = self.PIPE_Y
        for x, y, lbl, fg in [
            (52,                    PY+11, '6"-W-101', T.PIPE_WATER),
            (320,                   PY+11, '6"-W-101', T.PIPE_WATER),
            (605,                   PY+11, '6"-T-201', T.PIPE_TREATED),
            (self.NAOH_TANK_CX+16, self.DP_CY, '2"-C-301', T.PIPE_CHEM),
        ]:
            self.create_text(x, y, text=lbl, fill=fg, font=T.FONT_PID, anchor="center")

    def _draw_tag_labels(self):
        PY = self.PIPE_Y
        tags = [
            (32,                                    PY+30,  "V-101"),
            (self.P101_CX,                          PY+40,  "P-101"),
            (self.FT101_CX,                         PY+25,  "FT-101"),
            ((self.TANK_L+self.TANK_R)//2,          self.TANK_T-15, "TK-101  CHEMICAL MIXING ZONE"),
            (self.PH_CX,                            PY-44,  "AT-101\npH"),
            (self.NAOH_TANK_CX,                     self.NAOH_TANK_T-13, "TK-102  NaOH"),
            (self.NAOH_TANK_CX,                     self.DP_CY+33, "DP-101"),
            (self.FT102_CX,                         PY+25,  "FT-102"),
            ((self.FILT_L+self.FILT_R)//2,          self.TANK_T-14, "F-101"),
            (self.CL_CX,                            7,      "TK-103  Cl\u2082"),
            (self.CL_CX,                            108,    "DP-102"),
            (self.P102_CX,                          PY+40,  "P-102"),
            (self.FT103_CX,                         PY+25,  "FT-103"),
            (self.TANK_L-18,                        PY-33,  "LT-101"),
        ]
        for x, y, lbl in tags:
            self.create_text(x, y, text=lbl, fill=T.BG_DARK,
                             font=T.FONT_PID_B, anchor="center", justify="center")

    # ── Dynamic update ─────────────────────────────────────────────────────
    def update_data(self, data: dict, blink: bool):
        self._data  = data
        self._blink = blink
        pump_main   = data.get("coil_main",   True)
        pump_dosing = data.get("coil_dosing", True)
        pump_chlor  = data.get("coil_chlor",  True)
        estop       = data.get("coil_estop",  False)
        sp_naoh     = data.get("sp_naoh",     111)
        naoh_tank   = data.get("naoh_tank",   80)
        is_attack   = sp_naoh > 500

        if estop:
            pump_main = pump_dosing = pump_chlor = False

        self._update_pump("pump_p101",  self.P101_CX, self.PIPE_Y, pump_main)
        self._update_pump("pump_p102",  self.P102_CX, self.PIPE_Y, pump_main)
        self._update_pump("pump_dp101", self.NAOH_TANK_CX, self.DP_CY, pump_dosing)
        self._update_pump("pump_dp102", self.CL_CX, 96, pump_chlor, size=36)
        self._update_naoh_tank(naoh_tank)
        self._update_attack_indicator(is_attack, blink, sp_naoh)

    def _update_pump(self, tag, cx, cy, running, size=56):
        self.delete(tag)
        fn = A.make_dosing_pump if "dp" in tag else A.make_pump
        self._place_pil(fn(size, running=running), cx, cy, tag=tag)

    def _update_naoh_tank(self, level_pct):
        self.delete("tank_naoh")
        self._place_pil(A.make_chemical_tank(54, 68, int(level_pct), "NaOH"),
                        self.NAOH_TANK_CX, self.NAOH_TANK_T+34,
                        "tank_naoh", anchor_tl=True,
                        x0=self.NAOH_TANK_CX-27, y0=self.NAOH_TANK_T)

    def _update_attack_indicator(self, is_attack, blink, sp_naoh):
        self.delete("attack_indicator")
        if is_attack:
            tx = (self.TANK_L + self.TANK_R) // 2
            ty = self.TANK_B - 18
            bg_c = T.STATUS_STOP if blink else T.STATUS_STOP2
            self.create_rectangle(tx-120, ty-13, tx+120, ty+13,
                                  fill=bg_c, outline=T.BEVEL_DARKER, width=1,
                                  tags="attack_indicator")
            self.create_text(tx, ty,
                             text=f"!! NaOH SETPOINT TAMPERED: {sp_naoh:.0f} ppm !!",
                             fill=T.TEXT_WHITE, font=T.FONT_PID_B,
                             tags="attack_indicator")


# ══════════════════════════════════════════════════════════════════════════════
#  DigitalDisplay — Industrial digital readout block
# ══════════════════════════════════════════════════════════════════════════════
class DigitalDisplay(tk.Frame):
    BAR_W = 118; BAR_H = 6

    def __init__(self, parent, tag, name, unit, lo, hi,
                 alarm_hi=None, alarm_lo=None, width_chars=8, **kw):
        super().__init__(parent, bg=T.BG_MAIN, relief="raised", bd=2, **kw)
        self._lo, self._hi = lo, hi
        self._alarm_hi, self._alarm_lo = alarm_hi, alarm_lo
        self._alarm = False

        # Tag header row
        top = tk.Frame(self, bg=T.BG_PANEL, relief="flat")
        top.pack(fill="x")
        # Colored left tab based on alarm type
        tk.Frame(top, bg=T.BG_ACCENT, width=3).pack(side="left", fill="y")
        tk.Label(top, text=f" {tag}", bg=T.BG_PANEL, fg=T.BG_DARK,
                 font=T.FONT_PID_B, anchor="w").pack(side="left")
        tk.Label(top, text=f"{name} ", bg=T.BG_PANEL, fg=T.TEXT_MED,
                 font=T.FONT_PID, anchor="e").pack(side="right")

        # Value readout
        mid = tk.Frame(self, bg=T.BG_MAIN)
        mid.pack(fill="x", padx=3, pady=1)

        self._val_lbl = tk.Label(mid, text=" ----.--", bg=T.DISP_BG, fg=T.DISP_TEXT,
                                  font=T.FONT_VALUE_LG, anchor="e",
                                  relief="sunken", bd=2, width=width_chars,
                                  padx=4, pady=2)
        self._val_lbl.pack(side="left")
        tk.Label(mid, text=f" {unit}", bg=T.BG_MAIN, fg=T.TEXT_MED,
                 font=T.FONT_SMALL_B).pack(side="left", anchor="s")

        # Status LED
        self._status_cv = tk.Canvas(mid, width=14, height=14,
                                     bg=T.BG_MAIN, bd=0, highlightthickness=0)
        self._status_cv.pack(side="right", padx=4)
        self._dot = self._status_cv.create_oval(1, 1, 13, 13,
                                                  fill=T.STATUS_OK2, outline=T.BEVEL_DARK)

        # Bar graph
        bot = tk.Frame(self, bg=T.BG_MAIN)
        bot.pack(fill="x", padx=3, pady=(0, 3))
        self._bar_bg = tk.Canvas(bot, width=self.BAR_W, height=self.BAR_H,
                                  bg=T.BEVEL_MID, bd=0, highlightthickness=0,
                                  relief="sunken")
        self._bar_bg.pack(side="left")
        self._bar = self._bar_bg.create_rectangle(0, 0, 0, self.BAR_H,
                                                   fill=T.STATUS_OK2, outline="")

    def set_value(self, val: float):
        fmt = f"{val:8.1f}" if abs(val) < 10000 else f"{val:8.0f}"
        self._val_lbl.config(text=fmt)

        pct = max(0.0, min(1.0, (val - self._lo) / max(1, self._hi - self._lo)))
        self._bar_bg.coords(self._bar, 0, 0, int(self.BAR_W * pct), self.BAR_H)

        is_alarm = (
            (self._alarm_hi is not None and val > self._alarm_hi) or
            (self._alarm_lo is not None and val < self._alarm_lo)
        )
        self._alarm = is_alarm
        clr = T.STATUS_STOP2 if is_alarm else T.STATUS_OK2
        self._val_lbl.config(fg=T.DISP_ALRM if is_alarm else T.DISP_TEXT)
        self._bar_bg.itemconfig(self._bar,    fill=clr)
        self._status_cv.itemconfig(self._dot, fill=clr)

    def blink(self, state: bool):
        if self._alarm:
            c = T.STATUS_STOP2 if state else T.BEVEL_MID
            self._status_cv.itemconfig(self._dot, fill=c)


# ══════════════════════════════════════════════════════════════════════════════
#  AlarmAnnunciator — Classic SCADA alarm tiles (dark navy panel)
# ══════════════════════════════════════════════════════════════════════════════
class AlarmAnnunciator(tk.Frame):
    ALARM_DEFS = [
        (0, "AT-101\npH HIGH",     "#8B1A10"),
        (1, "AT-101\npH LOW",      "#8B1A10"),
        (2, "AT-102\nNaOH DANGER", "#B03A2E"),
        (3, "FT-101\nFLOW LOW",    "#784212"),
        (4, "TRB-101\nTURBID HI",  "#7D6608"),
        (5, "PT-101\nPRESS HIGH",  "#1A5276"),
        (6, "LT-102\nNaOH EMPTY",  "#4A235A"),
    ]

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=T.BG_ALARM, relief="sunken", bd=3, **kw)
        self._active_bits = 0
        self._tile_frames = {}

        hdr = tk.Frame(self, bg=T.BG_ALARM)
        hdr.pack(fill="x", padx=2, pady=(3, 0))
        # Accent tab
        tk.Frame(hdr, bg=T.STATUS_STOP, width=4).pack(side="left", fill="y")
        tk.Label(hdr, text="  ALARM ANNUNCIATOR", bg=T.BG_ALARM,
                 fg=T.TEXT_ALARM, font=T.FONT_SMALL_B, anchor="w").pack(side="left",
                                                                          padx=2, pady=2)
        tk.Label(hdr, text="ISA-18.2  ", bg=T.BG_ALARM, fg="#4A6278",
                 font=T.FONT_PID, anchor="e").pack(side="right")

        tile_row = tk.Frame(self, bg=T.BG_ALARM)
        tile_row.pack(fill="x", padx=6, pady=(4, 6))

        for i, (bit, name, accent) in enumerate(self.ALARM_DEFS):
            frm = tk.Frame(tile_row, bg=T.BG_ALARM)
            frm.grid(row=0, column=i, padx=3)
            cv = tk.Canvas(frm, width=80, height=56,
                           bg=T.BG_ALARM, bd=0, highlightthickness=0)
            cv.pack()
            self._tile_frames[bit] = cv
            self._draw_tile(cv, name, False, False, accent)

    def _draw_tile(self, cv, name, active, blink, accent):
        cv.delete("all")
        W, H = 80, 56

        if active and blink:
            bg_hex = accent
            fg = (255, 255, 255)
        elif active:
            r, g, b = int(accent[1:3], 16), int(accent[3:5], 16), int(accent[5:7], 16)
            r2, g2, b2 = min(255, r+70), min(255, g+70), min(255, b+70)
            bg_hex = f"#{r2:02X}{g2:02X}{b2:02X}"
            fg = (255, 240, 230)
        else:
            bg_hex = "#1A5C2A"   # normal — dark green (not black)
            fg = (169, 223, 191)

        cv.create_rectangle(1, 1, W-2, H-2, fill=bg_hex, outline=T.BG_ALARM, width=1)

        # Inner bevel for 3-D tile effect
        r, g, b = int(bg_hex[1:3], 16), int(bg_hex[3:5], 16), int(bg_hex[5:7], 16)
        hi  = f"#{min(255,r+40):02X}{min(255,g+40):02X}{min(255,b+40):02X}"
        sh  = f"#{max(0,r-30):02X}{max(0,g-30):02X}{max(0,b-30):02X}"
        cv.create_line(2, 2, W-3, 2, fill=hi)
        cv.create_line(2, 2, 2, H-3, fill=hi)
        cv.create_line(2, H-3, W-3, H-3, fill=sh)
        cv.create_line(W-3, 2, W-3, H-3, fill=sh)

        # LED indicator (top-right corner)
        led_c = "#E74C3C" if active else "#27AE60"
        cv.create_oval(W-14, 4, W-4, 14, fill=led_c, outline=T.BG_ALARM)
        # LED inner glow
        led_hi = "#FF8888" if active else "#7DCEA0"
        cv.create_oval(W-11, 6, W-8, 9, fill=led_hi, outline="")

        # Alarm name
        lines = name.split("\n")
        y0 = 17 if len(lines) > 1 else 22
        fg_hex = f"#{fg[0]:02X}{fg[1]:02X}{fg[2]:02X}"
        for j, line in enumerate(lines):
            cv.create_text(W//2, y0 + j*13, text=line,
                           fill=fg_hex, font=T.FONT_PID_B, anchor="center")

        # Status text
        status = "ALARM" if active else "NORMAL"
        s_col  = "#F1948A" if active else "#58D68D"
        cv.create_text(W//2, H-9, text=status, fill=s_col,
                       font=("Courier New", 7, "bold"), anchor="center")

    def update_alarms(self, alarm_bits, blink):
        for bit, name, accent in self.ALARM_DEFS:
            active = bool(alarm_bits & (1 << bit))
            self._draw_tile(self._tile_frames[bit], name, active, blink, accent)
        self._active_bits = alarm_bits


# ══════════════════════════════════════════════════════════════════════════════
#  EventLog — Timestamped event list (dark navy, NOT black)
# ══════════════════════════════════════════════════════════════════════════════
class EventLog(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=T.BG_ALARM, relief="sunken", bd=2, **kw)

        hdr = tk.Frame(self, bg=T.BG_DARK)
        hdr.pack(fill="x")
        tk.Frame(hdr, bg=T.BG_ACCENT, width=4).pack(side="left", fill="y")
        tk.Label(hdr, text="  EVENT LOG", bg=T.BG_DARK, fg=T.TEXT_WHITE,
                 font=T.FONT_SMALL_B).pack(side="left", padx=2, pady=2)
        tk.Label(hdr, text="DATE/TIME           DESCRIPTION",
                 bg=T.BG_DARK, fg="#7F9EAE",
                 font=("Courier New", 7)).pack(side="left", padx=8)

        txt_frame = tk.Frame(self, bg=T.BG_ALARM)
        txt_frame.pack(fill="both", expand=True, padx=1, pady=1)

        self._txt = tk.Text(txt_frame, height=5, bg=T.BG_ALARM,
                             fg=T.TEXT_ALARM, font=("Courier New", 8),
                             bd=0, highlightthickness=0, state="disabled",
                             cursor="arrow", insertbackground=T.TEXT_ALARM,
                             selectbackground=T.BG_DARK)
        sb = tk.Scrollbar(txt_frame, command=self._txt.yview,
                          bg=T.BG_DARK, width=11, troughcolor=T.BG_ALARM)
        self._txt.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._txt.pack(fill="both", expand=True)

        # Color tags — readable on dark navy background
        self._txt.tag_config("alarm",   foreground="#E74C3C")    # red
        self._txt.tag_config("restore", foreground="#27AE60")    # green
        self._txt.tag_config("info",    foreground="#AEB6BF")    # gray
        self._txt.tag_config("warn",    foreground="#E59866")    # amber

    def add(self, msg, level="info"):
        ts   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"  {ts}  {msg}\n"
        self._txt.config(state="normal")
        self._txt.insert("end", line, level)
        self._txt.see("end")
        self._txt.config(state="disabled")


# ══════════════════════════════════════════════════════════════════════════════
#  TrendChart — Dual-pen rolling trend
# ══════════════════════════════════════════════════════════════════════════════
class TrendChart(tk.Frame):
    HIST  = 120
    PAD_L = 52; PAD_R = 52; PAD_T = 26; PAD_B = 28

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=T.BG_PANEL, relief="sunken", bd=2, **kw)
        self.ph_hist   = deque([7.2]   * self.HIST, maxlen=self.HIST)
        self.naoh_hist = deque([111.0] * self.HIST, maxlen=self.HIST)

        hdr = tk.Frame(self, bg=T.BG_DARK)
        hdr.pack(fill="x")
        tk.Frame(hdr, bg=T.STATUS_OK, width=4).pack(side="left", fill="y")
        tk.Label(hdr, text="  TREND RECORDER  —  pH (blue)  |  NaOH ppm (red)  |  last 120 s",
                 bg=T.BG_DARK, fg=T.TEXT_WHITE, font=T.FONT_SMALL_B,
                 anchor="w").pack(side="left", padx=2, pady=2)

        self._cv = tk.Canvas(self, bg="#EEF0E8", bd=0, highlightthickness=0)
        self._cv.pack(fill="both", expand=True, padx=2, pady=2)
        self._cv.bind("<Configure>", self._on_resize)

        self._chart_w = 600
        self._draw_frame()

    def _on_resize(self, e):
        self._chart_w = e.width
        self._draw_frame()
        self._redraw_lines()

    def _cx(self, idx):
        return int(self.PAD_L + (idx/(self.HIST-1)) * (self._chart_w - self.PAD_L - self.PAD_R))

    def _ph_y(self, val):
        h = self._cv.winfo_height() or 130
        return int((h - self.PAD_B) - (max(0, min(14, val)) / 14.0) * (h - self.PAD_T - self.PAD_B))

    def _naoh_y(self, val):
        h = self._cv.winfo_height() or 130
        return int((h - self.PAD_B) - (max(0, min(600, val)) / 600.0) * (h - self.PAD_T - self.PAD_B))

    def _draw_frame(self):
        c = self._cv
        c.delete("frame")
        h = c.winfo_height() or 130
        w = self._chart_w
        CL, CR, CT, CB = self.PAD_L, w - self.PAD_R, self.PAD_T, h - self.PAD_B

        # Chart area — warm cream paper
        c.create_rectangle(CL, CT, CR, CB, fill="#FAFBF2",
                            outline=T.BEVEL_DARK, width=1, tags="frame")

        # Horizontal grid
        for ph_val, lbl in [(14, "14"), (8.5, "8.5"), (7, "7.0"), (0, "0")]:
            yy = self._ph_y(ph_val)
            alarm_line = ph_val == 8.5
            c.create_line(CL, yy, CR, yy,
                          fill="#FFCCCC" if alarm_line else "#E0E4D8",
                          width=1, dash=(4, 4) if alarm_line else (2, 6),
                          tags="frame")
            c.create_text(CL-4, yy, text=lbl, fill=T.BG_DARK,
                          font=T.FONT_PID, anchor="e", tags="frame")

        # Right axis (NaOH)
        for naoh_val, lbl in [(600, "600"), (200, "200"), (0, "0")]:
            yy = self._naoh_y(naoh_val)
            if naoh_val == 200:
                c.create_line(CL, yy, CR, yy, fill="#FFCCCC",
                              width=1, dash=(4, 4), tags="frame")
            c.create_text(CR+4, yy, text=lbl, fill=T.STATUS_STOP,
                          font=T.FONT_PID, anchor="w", tags="frame")

        # Axis titles
        c.create_text(CL-38, (CT+CB)//2, text="pH",
                      fill=T.PIPE_WATER, font=T.FONT_PID_B, tags="frame")
        c.create_text(CR+38, (CT+CB)//2, text="ppm",
                      fill=T.STATUS_STOP, font=T.FONT_PID_B, tags="frame")
        c.create_text((CL+CR)//2, h-7,
                      text="\u2190 120 sec ago               NOW \u2192",
                      fill=T.TEXT_LIGHT, font=T.FONT_PID, tags="frame")

        # Legend box
        c.create_rectangle(CR-122, CT+2, CR-2, CT+30,
                           fill="#FAFBF2", outline=T.BEVEL_DARK, tags="frame")
        c.create_line(CR-117, CT+10, CR-92, CT+10, fill=T.PIPE_WATER, width=2, tags="frame")
        c.create_text(CR-88, CT+10, text="pH",    fill=T.PIPE_WATER,  font=T.FONT_PID,
                      anchor="w", tags="frame")
        c.create_line(CR-117, CT+22, CR-92, CT+22, fill=T.STATUS_STOP, width=2, tags="frame")
        c.create_text(CR-88, CT+22, text="NaOH",  fill=T.STATUS_STOP, font=T.FONT_PID,
                      anchor="w", tags="frame")

        # Alarm threshold label
        c.create_text(CL+44, self._ph_y(8.5)-7, text="pH alarm 8.50",
                      fill=T.STATUS_STOP, font=T.FONT_PID, tags="frame")

        c.create_line(0, 0, 0, 0, fill=T.PIPE_WATER,  width=2, smooth=True, tags="ph_line")
        c.create_line(0, 0, 0, 0, fill=T.STATUS_STOP, width=2, smooth=True, tags="naoh_line")

    def push(self, ph, naoh):
        self.ph_hist.append(ph)
        self.naoh_hist.append(naoh)
        self._redraw_lines()

    def _redraw_lines(self):
        if not self._cv.winfo_exists():
            return
        ph_pts, naoh_pts = [], []
        for i, (ph_v, naoh_v) in enumerate(zip(self.ph_hist, self.naoh_hist)):
            ph_pts   += [self._cx(i), self._ph_y(ph_v)]
            naoh_pts += [self._cx(i), self._naoh_y(naoh_v)]
        if len(ph_pts) >= 4:
            self._cv.coords("ph_line",   *ph_pts)
            self._cv.coords("naoh_line", *naoh_pts)


# ══════════════════════════════════════════════════════════════════════════════
#  SetpointPanel — Operator setpoint & actuator control
# ══════════════════════════════════════════════════════════════════════════════
class SetpointPanel(tk.Frame):
    def __init__(self, parent, on_write_register, on_write_coil, **kw):
        super().__init__(parent, bg=T.BG_MAIN, relief="raised", bd=2, **kw)
        self._wreg  = on_write_register
        self._wcoil = on_write_coil
        self._coil_state = {}
        self._estop = False
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg=T.BG_TOPBAR)
        hdr.pack(fill="x")
        tk.Frame(hdr, bg=T.STATUS_WARN, width=4).pack(side="left", fill="y")
        tk.Label(hdr, text="  OPERATOR CONTROL STATION",
                 bg=T.BG_TOPBAR, fg=T.TEXT_WHITE, font=T.FONT_TITLE,
                 anchor="w").pack(side="left", padx=2, pady=3)
        tk.Label(hdr, text="Modbus Write  ", bg=T.BG_TOPBAR,
                 fg="#A9CCE3", font=T.FONT_PID).pack(side="right", padx=6)

        cols = tk.Frame(self, bg=T.BG_MAIN)
        cols.pack(fill="x", padx=4, pady=4)

        # ── Setpoints ──────────────────────────────────────────────────────
        sp_frame = bevel_frame(cols, raised=False)
        sp_frame.pack(side="left", fill="y", padx=(0, 6), ipadx=4, ipady=4)
        tk.Label(sp_frame, text=" SETPOINTS", bg=T.BG_PANEL,
                 fg=T.BG_DARK, font=T.FONT_SMALL_B, anchor="w").grid(
            row=0, column=0, columnspan=5, sticky="ew", pady=(0, 4))

        self._naoh_var = tk.StringVar(value="111")
        self._make_sp_row(sp_frame, 1, "NaOH SP", self._naoh_var, "ppm",
                          self._set_naoh, "[Normal: 111]")
        self._flow_var = tk.StringVar(value="520")
        self._make_sp_row(sp_frame, 2, "Flow SP", self._flow_var, "L/min",
                          self._set_flow, "[Design: 520]")

        # ── Actuator status ────────────────────────────────────────────────
        act_frame = bevel_frame(cols, raised=False)
        act_frame.pack(side="left", fill="y", padx=(0, 6), ipadx=4, ipady=4)
        tk.Label(act_frame, text=" ACTUATORS", bg=T.BG_PANEL,
                 fg=T.BG_DARK, font=T.FONT_SMALL_B, anchor="w").grid(
            row=0, column=0, columnspan=2, sticky="ew", pady=(0, 4))

        self._act_btns = {}
        acts = [
            (COIL_MAIN,   "P-101  MAIN PUMP"),
            (COIL_DOSING, "DP-101 DOSING PUMP"),
            (COIL_CHLOR,  "DP-102 CHLOR PUMP"),
            (COIL_OUTLET, "V-201  OUTLET VALVE"),
        ]
        for i, (coil, label) in enumerate(acts):
            cv = tk.Canvas(act_frame, width=14, height=14, bg=T.BG_PANEL,
                           bd=0, highlightthickness=0)
            cv.grid(row=i+1, column=0, padx=(4, 2), pady=2)
            dot = cv.create_oval(1, 1, 13, 13, fill=T.STATUS_OK2, outline=T.BEVEL_DARK)
            cv._dot = dot
            btn = tk.Button(
                act_frame, text=label, bg=T.BG_PANEL,
                fg=T.TEXT_DARK, font=T.FONT_SMALL, relief="raised", bd=2,
                padx=6, pady=2, anchor="w", width=18,
                activebackground=T.BG_DARK, activeforeground=T.TEXT_WHITE,
                cursor="hand2", command=lambda c=coil: self._toggle_coil(c)
            )
            btn.grid(row=i+1, column=1, padx=2, pady=2, sticky="ew")
            self._act_btns[coil] = (btn, cv)

        # ── Emergency control ──────────────────────────────────────────────
        em_frame = bevel_frame(cols, raised=False)
        em_frame.pack(side="left", fill="both", expand=True, ipadx=4, ipady=4)
        tk.Label(em_frame, text=" EMERGENCY", bg=T.BG_PANEL,
                 fg=T.BG_DARK, font=T.FONT_SMALL_B, anchor="w").pack(
            fill="x", pady=(0, 6))

        self._estop_btn = tk.Button(
            em_frame,
            text="  \u25a0  EMERGENCY SHUTDOWN",
            bg="#8B1A10", fg="#F5CBA7", font=T.FONT_LABEL_B,
            relief="raised", bd=3, padx=8, pady=6, anchor="w",
            activebackground=T.STATUS_STOP2, activeforeground=T.TEXT_WHITE,
            cursor="hand2", command=self._estop_toggle
        )
        self._estop_btn.pack(fill="x")

    def _make_sp_row(self, parent, row, label, var, unit, cmd, note=""):
        tk.Label(parent, text=f" {label}", bg=T.BG_PANEL, fg=T.TEXT_DARK,
                 font=T.FONT_SMALL_B, anchor="w", width=10).grid(
            row=row, column=0, sticky="w", pady=3, padx=(4, 0))
        entry = tk.Entry(parent, textvariable=var, width=7,
                         bg=T.DISP_BG, fg=T.DISP_TEXT,
                         insertbackground=T.TEXT_DARK,
                         font=T.FONT_VALUE, relief="sunken", bd=2)
        entry.grid(row=row, column=1, padx=4, pady=3)
        tk.Label(parent, text=unit, bg=T.BG_PANEL, fg=T.TEXT_MED,
                 font=T.FONT_SMALL, width=5, anchor="w").grid(row=row, column=2)
        tk.Button(parent, text="WRITE", bg=T.BG_DARK, fg=T.TEXT_WHITE,
                  font=T.FONT_SMALL_B, relief="raised", bd=2, padx=6,
                  activebackground=T.STATUS_OK, cursor="hand2",
                  command=cmd).grid(row=row, column=3, padx=4)
        tk.Label(parent, text=note, bg=T.BG_PANEL, fg=T.TEXT_LIGHT,
                 font=T.FONT_PID).grid(row=row, column=4, padx=4)

    def _set_naoh(self):
        try:
            val = int(float(self._naoh_var.get()))
            self._wreg(HR_NAOH_SP, max(0, min(65535, val)))
        except ValueError:
            pass

    def _set_flow(self):
        try:
            self._wreg(HR_FLOW_SP, int(float(self._flow_var.get())))
        except ValueError:
            pass

    def _toggle_coil(self, coil):
        self._wcoil(coil, not self._coil_state.get(coil, True))

    def _estop_toggle(self):
        self._estop = not self._estop
        self._wcoil(COIL_ESTOP, self._estop)
        if self._estop:
            self._estop_btn.config(bg=T.STATUS_STOP2, fg=T.TEXT_WHITE,
                                    text="  \u25a0  E-STOP ACTIVE — Click to Reset")
        else:
            self._estop_btn.config(bg="#8B1A10", fg="#F5CBA7",
                                    text="  \u25a0  EMERGENCY SHUTDOWN")

    def update_data(self, data: dict):
        self._naoh_var.set(str(int(data.get("sp_naoh", 111))))
        self._flow_var.set(str(int(data.get("sp_flow", 520))))

        coil_map = {
            COIL_MAIN:   "coil_main",
            COIL_DOSING: "coil_dosing",
            COIL_OUTLET: "coil_outlet",
            COIL_CHLOR:  "coil_chlor",
        }
        for coil, key in coil_map.items():
            on = data.get(key, True)
            self._coil_state[coil] = on
            if coil in self._act_btns:
                btn, cv = self._act_btns[coil]
                btn.config(fg=T.STATUS_OK if on else T.STATUS_STOP)
                cv.itemconfig(cv._dot, fill=T.STATUS_OK2 if on else T.STATUS_STOP2)

        estop = data.get("coil_estop", False)
        if estop != self._estop:
            self._estop = estop
            if estop:
                self._estop_btn.config(bg=T.STATUS_STOP2, fg=T.TEXT_WHITE,
                                        text="  \u25a0  E-STOP ACTIVE — Click to Reset")
            else:
                self._estop_btn.config(bg="#8B1A10", fg="#F5CBA7",
                                        text="  \u25a0  EMERGENCY SHUTDOWN")


# ══════════════════════════════════════════════════════════════════════════════
#  SCADAApp — Main window
# ══════════════════════════════════════════════════════════════════════════════
class SCADAApp(tk.Tk):
    POLL_MS = 900

    def __init__(self, host: str, port: int):
        super().__init__()
        self.title(f"{APP_NAME}  —  {APP_PLANT}  {APP_VERSION}")
        self.configure(bg=T.BG_ROOT)
        self.geometry(f"{T.WIN_W}x{T.WIN_H}")
        self.minsize(1100, 720)

        self._host        = host
        self._port        = port
        self._data_q      = queue.Queue(maxsize=20)
        self._cmd_q       = queue.Queue()
        self._last_data   = {}
        self._blink       = False
        self._tick        = 0
        self._connected   = False
        self._prev_attack = False

        self._build_menubar()
        self._build_titlebar()
        self._build_body()
        self._build_statusbar()

        self._poller = ModbusPoller(host, port, self._data_q, self._cmd_q)
        self._poller.start()

        self.after(self.POLL_MS, self._loop)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Menu bar ──────────────────────────────────────────────────────────
    def _build_menubar(self):
        menubar = tk.Menu(self, bg=T.BG_PANEL, fg=T.TEXT_DARK,
                          activebackground=T.BG_DARK, activeforeground=T.TEXT_WHITE,
                          relief="flat", bd=0, font=T.FONT_MENU)
        self.config(menu=menubar)

        # File
        file_menu = tk.Menu(menubar, tearoff=0, bg=T.BG_PANEL, fg=T.TEXT_DARK,
                            activebackground=T.BG_DARK, activeforeground=T.TEXT_WHITE,
                            font=T.FONT_MENU)
        file_menu.add_command(label="Connect...",    command=self._menu_connect)
        file_menu.add_command(label="Disconnect",    command=self._menu_disconnect)
        file_menu.add_separator()
        file_menu.add_command(label="Exit",          command=self._on_close)
        menubar.add_cascade(label=" File ", menu=file_menu)

        # View
        view_menu = tk.Menu(menubar, tearoff=0, bg=T.BG_PANEL, fg=T.TEXT_DARK,
                            activebackground=T.BG_DARK, activeforeground=T.TEXT_WHITE,
                            font=T.FONT_MENU)
        self._show_trend    = tk.BooleanVar(value=True)
        self._show_events   = tk.BooleanVar(value=True)
        self._show_alarms   = tk.BooleanVar(value=True)
        self._show_controls = tk.BooleanVar(value=True)
        view_menu.add_checkbutton(label="Show Trend Chart",
                                  variable=self._show_trend,
                                  command=self._toggle_trend)
        view_menu.add_checkbutton(label="Show Event Log",
                                  variable=self._show_events,
                                  command=self._toggle_events)
        view_menu.add_checkbutton(label="Show Alarm Panel",
                                  variable=self._show_alarms,
                                  command=self._toggle_alarms)
        view_menu.add_checkbutton(label="Show Operator Controls",
                                  variable=self._show_controls,
                                  command=self._toggle_controls)
        menubar.add_cascade(label=" View ", menu=view_menu)

        # Monitoring
        mon_menu = tk.Menu(menubar, tearoff=0, bg=T.BG_PANEL, fg=T.TEXT_DARK,
                           activebackground=T.BG_DARK, activeforeground=T.TEXT_WHITE,
                           font=T.FONT_MENU)
        mon_menu.add_command(label="Clear Event Log",    command=self._clear_evlog)
        mon_menu.add_command(label="Reset Trend Chart",  command=self._reset_trend)
        mon_menu.add_separator()
        mon_menu.add_command(label="Connection Info...", command=self._show_conn_info)
        menubar.add_cascade(label=" Monitoring ", menu=mon_menu)

        # Help
        help_menu = tk.Menu(menubar, tearoff=0, bg=T.BG_PANEL, fg=T.TEXT_DARK,
                            activebackground=T.BG_DARK, activeforeground=T.TEXT_WHITE,
                            font=T.FONT_MENU)
        help_menu.add_command(label="About ICSSI SCADA...", command=self._show_about)
        menubar.add_cascade(label=" Help ", menu=help_menu)

    # ── Title bar ─────────────────────────────────────────────────────────
    def _build_titlebar(self):
        # Thin accent stripe at very top
        tk.Frame(self, bg=T.BG_ACCENT, height=3).pack(fill="x")

        bar = tk.Frame(self, bg=T.BG_TOPBAR, height=52)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        # Left: ICSSI emblem + branding
        left = tk.Frame(bar, bg=T.BG_TOPBAR)
        left.pack(side="left", fill="y", padx=8)

        emblem_img = A.make_icssi_emblem(42)
        photo = ImageTk.PhotoImage(emblem_img)
        lbl_logo = tk.Label(left, image=photo, bg=T.BG_TOPBAR)
        lbl_logo.image = photo   # keep reference
        lbl_logo.pack(side="left", pady=4)

        brand = tk.Frame(left, bg=T.BG_TOPBAR)
        brand.pack(side="left", fill="y", padx=8)
        tk.Label(brand, text=APP_NAME, bg=T.BG_TOPBAR,
                 fg=T.TEXT_WHITE, font=T.FONT_TOPBAR).pack(anchor="w", pady=(6, 0))
        tk.Label(brand, text=APP_FULL, bg=T.BG_TOPBAR,
                 fg=T.TEXT_TOPBAR, font=T.FONT_TOPBAR_S).pack(anchor="w")

        # Vertical separator
        tk.Frame(bar, bg=T.BG_TOPBAR2, width=2).pack(side="left", fill="y", padx=8)

        # Center: plant name + attack banner
        center = tk.Frame(bar, bg=T.BG_TOPBAR)
        center.pack(side="left", expand=True)
        tk.Label(center, text=APP_PLANT, bg=T.BG_TOPBAR,
                 fg=T.TEXT_WHITE, font=T.FONT_TOPBAR).pack()
        self._attack_banner = tk.Label(
            center, text="STATUS: NORMAL OPERATION",
            bg=T.BG_TOPBAR, fg="#27AE60", font=T.FONT_SMALL_B
        )
        self._attack_banner.pack()

        # Right: clock + connection
        right = tk.Frame(bar, bg=T.BG_TOPBAR)
        right.pack(side="right", fill="y", padx=12)
        self._lbl_time = tk.Label(right, text="--:--:--", bg=T.BG_TOPBAR,
                                   fg=T.TEXT_WHITE, font=T.FONT_VALUE_LG)
        self._lbl_time.pack(anchor="e", pady=(5, 0))
        self._lbl_conn = tk.Label(right, text="\u25cf CONNECTING...", bg=T.BG_TOPBAR,
                                   fg=T.STATUS_WARN2, font=T.FONT_SMALL_B)
        self._lbl_conn.pack(anchor="e")

        # Bottom separator stripe
        tk.Frame(self, bg=T.BEVEL_DARKER, height=2).pack(fill="x")

    # ── Body layout ───────────────────────────────────────────────────────
    def _build_body(self):
        body = tk.Frame(self, bg=T.BG_ROOT)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)
        self._body = body
        self._build_left(body)
        self._build_right(body)

    def _build_left(self, parent):
        left = tk.Frame(parent, bg=T.BG_MAIN)
        left.grid(row=0, column=0, sticky="nsew", padx=(4, 2), pady=4)
        left.rowconfigure(0, weight=0)
        left.rowconfigure(1, weight=0)
        left.rowconfigure(2, weight=1)
        left.rowconfigure(3, weight=0)
        left.columnconfigure(0, weight=1)

        # ── P&ID diagram ──────────────────────────────────────────────────
        pid_outer = bevel_frame(left, raised=False)
        pid_outer.grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 2))

        pid_hdr = tk.Frame(pid_outer, bg=T.BG_DARK)
        pid_hdr.pack(fill="x")
        tk.Frame(pid_hdr, bg=T.BG_ACCENT, width=4).pack(side="left", fill="y")
        tk.Label(pid_hdr, text="  P&ID — PROCESS FLOW DIAGRAM", bg=T.BG_DARK,
                 fg=T.TEXT_WHITE, font=T.FONT_SMALL_B, anchor="w").pack(
            side="left", padx=2, pady=2)
        tk.Label(pid_hdr, text="DWG: WWTP-P01-001  Rev.3  ",
                 bg=T.BG_DARK, fg="#7F9EAE", font=T.FONT_PID).pack(side="right", padx=4)

        self.pid = PIDCanvas(pid_outer)
        self.pid.pack(padx=2, pady=2)

        # ── Alarm annunciator ─────────────────────────────────────────────
        self.annunciator = AlarmAnnunciator(left)
        self._annunciator_row = self.annunciator
        self.annunciator.grid(row=1, column=0, sticky="ew", padx=4, pady=2)

        # ── Trend chart ───────────────────────────────────────────────────
        self.trend = TrendChart(left)
        self._trend_row = self.trend
        self.trend.grid(row=2, column=0, sticky="nsew", padx=4, pady=2)

        # ── Operator control ──────────────────────────────────────────────
        self.ctrl = SetpointPanel(
            left,
            on_write_register=self._cmd_write_reg,
            on_write_coil=self._cmd_write_coil,
        )
        self._ctrl_row = self.ctrl
        self.ctrl.grid(row=3, column=0, sticky="ew", padx=4, pady=(2, 4))

    def _build_right(self, parent):
        right = tk.Frame(parent, bg=T.BG_MAIN)
        right.grid(row=0, column=1, sticky="nsew", padx=(2, 4), pady=4)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)
        right.rowconfigure(2, weight=0)

        # ── Section header ────────────────────────────────────────────────
        rhdr = tk.Frame(right, bg=T.BG_DARK)
        rhdr.grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 0))
        tk.Frame(rhdr, bg=T.BG_ACCENT, width=4).pack(side="left", fill="y")
        tk.Label(rhdr, text="  PROCESS VARIABLES  — LIVE READOUT",
                 bg=T.BG_DARK, fg=T.TEXT_WHITE, font=T.FONT_SMALL_B,
                 anchor="w").pack(side="left", padx=2, pady=3)
        tk.Label(rhdr, text="1 s scan  ",
                 bg=T.BG_DARK, fg="#7F9EAE", font=T.FONT_PID).pack(side="right")

        # ── Readout grid ──────────────────────────────────────────────────
        rgrid = bevel_frame(right, raised=False)
        rgrid.grid(row=1, column=0, sticky="nsew", padx=4, pady=2)
        rgrid.columnconfigure(0, weight=1)
        rgrid.columnconfigure(1, weight=1)

        readout_defs = [
            ("AT-101",  "pH",           "",      0,  14,   8.50,  6.20),
            ("AT-102",  "NaOH Actual",  "ppm",   0, 500, 200.0,   None),
            ("FT-101",  "Flow In",      "L/min", 0, 1000, None,   200),
            ("FT-103",  "Flow Out",     "L/min", 0, 1000, None,   None),
            ("PT-101",  "Pressure",     "PSI",   0,  100,  70.0,  None),
            ("LT-101",  "Water Level",  "cm",    0,  300, 290.0,   80),
            ("LT-102",  "NaOH Tank",    "%",     0,  100,  None,    5),
            ("TRB-101", "Turbidity",    "NTU",   0,   20,  10.0,  None),
            ("TT-101",  "Temperature",  "\u00b0C", 0, 50,  None,  None),
            ("FT-104",  "Chlorine",     "ppm",   0,    5,   4.0,  None),
        ]
        self._displays = {}
        disp_keys = ["ph", "naoh_actual", "flow_in", "flow_out", "pressure",
                     "water_level", "naoh_tank", "turbidity", "temperature", "chlorine"]

        for i, (cdef, key) in enumerate(zip(readout_defs, disp_keys)):
            tag, name, unit, lo, hi, alh, all_ = cdef
            disp = DigitalDisplay(rgrid, tag, name, unit, lo, hi, alh, all_)
            disp.grid(row=i//2, column=i%2, padx=4, pady=3, sticky="ew")
            self._displays[key] = disp

        # ── Event log ─────────────────────────────────────────────────────
        self.evlog = EventLog(right)
        self._evlog_row = self.evlog
        self.evlog.grid(row=2, column=0, sticky="ew", padx=4, pady=(2, 4))
        self.evlog.add("System started — connecting to Modbus server...", "info")

    # ── Status bar ────────────────────────────────────────────────────────
    def _build_statusbar(self):
        tk.Frame(self, bg=T.BEVEL_DARKER, height=2).pack(fill="x")

        sbar = tk.Frame(self, bg=T.BG_DARK, height=22)
        sbar.pack(fill="x")
        sbar.pack_propagate(False)

        sep = lambda: tk.Label(sbar, text=" \u2502 ", bg=T.BG_DARK,
                               fg=T.BEVEL_DARK, font=T.FONT_PID).pack(side="left")

        self._sb_conn = tk.Label(sbar, text=" \u25cf CONNECTING...", bg=T.BG_DARK,
                                  fg=T.STATUS_WARN2, font=T.FONT_PID)
        self._sb_conn.pack(side="left", padx=4)
        sep()

        self._sb_tick = tk.Label(sbar, text="Scan: 0", bg=T.BG_DARK,
                                  fg=T.TEXT_LIGHT, font=T.FONT_PID)
        self._sb_tick.pack(side="left")
        sep()

        self._sb_host = tk.Label(sbar, text=f"{self._host}:{self._port}",
                                  bg=T.BG_DARK, fg=T.TEXT_LIGHT, font=T.FONT_PID)
        self._sb_host.pack(side="left")

        tk.Label(sbar,
                 text=f"{APP_NAME}  |  {APP_FULL}  |  {APP_MODBUS}  |  {APP_VERSION}  ",
                 bg=T.BG_DARK, fg=T.TEXT_LIGHT, font=T.FONT_PID
                 ).pack(side="right", padx=6)

    # ── Update loop ───────────────────────────────────────────────────────
    def _loop(self):
        self._tick += 1
        self._blink = not self._blink
        self._lbl_time.config(text=datetime.now().strftime("%H:%M:%S"))
        self._sb_tick.config(text=f"Scan: {self._tick}")

        data = None
        while not self._data_q.empty():
            try:
                data = self._data_q.get_nowait()
            except queue.Empty:
                break

        if data is not None:
            if data.get("connected"):
                if not self._connected:
                    self.evlog.add(
                        f"Connected to {self._host}:{self._port}", "restore")
                self._connected = True
                self._last_data = data
                self._apply_data(data)
                conn_txt = f"\u25cf ONLINE  {self._host}:{self._port}"
                self._lbl_conn.config(text=conn_txt, fg=T.STATUS_OK2)
                self._sb_conn.config(text=f" \u25cf ONLINE  {self._host}:{self._port}",
                                     fg=T.STATUS_OK2)
            else:
                if self._connected:
                    self.evlog.add(
                        f"Connection lost — {self._host}:{self._port}", "alarm")
                self._connected = False
                self._lbl_conn.config(text="\u25cf OFFLINE", fg=T.STATUS_STOP2)
                self._sb_conn.config(text=" \u25cf OFFLINE — Retrying...",
                                     fg=T.STATUS_STOP2)
        elif self._last_data:
            self._blink_update()

        self.after(self.POLL_MS, self._loop)

    def _apply_data(self, data: dict):
        for key, disp in self._displays.items():
            disp.set_value(data.get(key, 0.0))
            disp.blink(self._blink)

        self.pid.update_data(data, self._blink)
        self.trend.push(data.get("ph", 7.2), data.get("naoh_actual", 111.0))

        alarm_bits = int(data.get("alarm", 0))
        self.annunciator.update_alarms(alarm_bits, self._blink)

        self.ctrl.update_data(data)

        # Attack banner
        sp_naoh   = data.get("sp_naoh", 111)
        is_attack = sp_naoh > 500

        if is_attack:
            txt = (f"!! SETPOINT TAMPERED — NaOH: {sp_naoh:.0f} ppm  "
                   f"(Normal: 111 ppm) — DANGER !!")
            fg = T.STATUS_STOP2 if self._blink else T.STATUS_WARN
            self._attack_banner.config(text=txt, fg=fg)
            self.title(f"!! ATTACK ACTIVE !!  {APP_NAME} — {APP_PLANT}")
        else:
            self._attack_banner.config(text="STATUS: NORMAL OPERATION", fg=T.STATUS_OK2)
            self.title(f"{APP_NAME}  —  {APP_PLANT}  {APP_VERSION}")

        if is_attack and not self._prev_attack:
            self.evlog.add(
                f"[ATTACK]  NaOH setpoint tampered: {sp_naoh:.0f} ppm  (was 111 ppm)",
                "alarm")
        elif not is_attack and self._prev_attack:
            self.evlog.add("[RESTORE] NaOH setpoint restored to normal: 111 ppm", "restore")

        self._prev_attack = is_attack

    def _blink_update(self):
        alarm_bits = int(self._last_data.get("alarm", 0))
        self.annunciator.update_alarms(alarm_bits, self._blink)
        sp_naoh = self._last_data.get("sp_naoh", 111)
        if sp_naoh > 500:
            fg = T.STATUS_STOP2 if self._blink else T.STATUS_WARN
            self._attack_banner.config(fg=fg)

    # ── Menu actions ──────────────────────────────────────────────────────
    def _menu_connect(self):
        dlg = ConnectDialog(self, self._host, self._port)
        self.wait_window(dlg)
        if dlg.result:
            host, port = dlg.result
            self._host = host
            self._port = port
            self._sb_host.config(text=f"{host}:{port}")
            self._poller.stop()
            self._data_q = queue.Queue(maxsize=20)
            self._cmd_q  = queue.Queue()
            self._poller = ModbusPoller(host, port, self._data_q, self._cmd_q)
            self._poller.start()
            self._connected = False
            self.evlog.add(f"Reconnecting to {host}:{port}...", "info")

    def _menu_disconnect(self):
        self._poller.stop()
        self._connected = False
        self._lbl_conn.config(text="\u25cf DISCONNECTED", fg=T.STATUS_UNKN)
        self._sb_conn.config(text=" \u25cf DISCONNECTED", fg=T.STATUS_UNKN)
        self.evlog.add("Manually disconnected.", "warn")

    def _toggle_trend(self):
        if self._show_trend.get():
            self._trend_row.grid()
        else:
            self._trend_row.grid_remove()

    def _toggle_events(self):
        if self._show_events.get():
            self._evlog_row.grid()
        else:
            self._evlog_row.grid_remove()

    def _toggle_alarms(self):
        if self._show_alarms.get():
            self._annunciator_row.grid()
        else:
            self._annunciator_row.grid_remove()

    def _toggle_controls(self):
        if self._show_controls.get():
            self._ctrl_row.grid()
        else:
            self._ctrl_row.grid_remove()

    def _clear_evlog(self):
        self.evlog._txt.config(state="normal")
        self.evlog._txt.delete("1.0", "end")
        self.evlog._txt.config(state="disabled")
        self.evlog.add("Event log cleared.", "info")

    def _reset_trend(self):
        self.trend.ph_hist   = deque([7.2]   * TrendChart.HIST, maxlen=TrendChart.HIST)
        self.trend.naoh_hist = deque([111.0] * TrendChart.HIST, maxlen=TrendChart.HIST)
        self.trend._draw_frame()
        self.trend._redraw_lines()

    def _show_conn_info(self):
        state = "ONLINE" if self._connected else "OFFLINE"
        info  = (f"Host:    {self._host}\n"
                 f"Port:    {self._port}\n"
                 f"State:   {state}\n"
                 f"Scan:    {self._tick}\n"
                 f"Protocol: Modbus TCP")
        dlg = tk.Toplevel(self)
        dlg.title("Connection Info")
        dlg.configure(bg=T.BG_MAIN)
        dlg.resizable(False, False)
        dlg.grab_set()
        tk.Frame(dlg, bg=T.BG_TOPBAR, height=6).pack(fill="x")
        tk.Label(dlg, text=info, bg=T.BG_MAIN, fg=T.TEXT_DARK,
                 font=("Courier New", 10), justify="left",
                 padx=20, pady=14).pack()
        tk.Button(dlg, text="  OK  ", bg=T.BG_DARK, fg=T.TEXT_WHITE,
                  font=T.FONT_SMALL_B, relief="raised", bd=2,
                  command=dlg.destroy).pack(pady=(0, 10))

    def _show_about(self):
        AboutDialog(self)

    # ── Commands ──────────────────────────────────────────────────────────
    def _cmd_write_reg(self, addr, val):
        self._poller.write_register(addr, val)

    def _cmd_write_coil(self, addr, val):
        self._poller.write_coil(addr, val)

    def _on_close(self):
        self._poller.stop()
        self.destroy()


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description=f"ICSSI WWTP SCADA Desktop {APP_VERSION}")
    parser.add_argument("--host", default="127.0.0.1",
                        help="OpenPLC / sensor server IP")
    parser.add_argument("--port", type=int, default=502,
                        help="Modbus TCP port (502=OpenPLC, 5020=sensor server)")
    args = parser.parse_args()

    app = SCADAApp(args.host, args.port)
    app.mainloop()


if __name__ == "__main__":
    main()
