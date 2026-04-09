"""
ICSSI ICS Cyber Ranges — SCADA Theme v3.0
Retro-enterprise industrial palette (Wonderware / Citect / iFIX style).
Zero pure black — darkest is deep navy #1A252F.
"""

# ── Background & Panel ─────────────────────────────────────────────────────────
BG_ROOT      = "#BDC3C7"   # Window chrome — cool steel gray
BG_MAIN      = "#D0D3D4"   # Main work area — classic SCADA silver-gray
BG_PANEL     = "#C5C9CC"   # Sub-panels & raised frames
BG_WIDGET    = "#EEF2F7"   # Display/entry widget bg — warm near-white
BG_DARK      = "#4A6278"   # Dark section headers — slate blue-gray
BG_TOPBAR    = "#1A3A5C"   # Title bar — deep navy
BG_TOPBAR2   = "#21618C"   # Secondary topbar — steel blue
BG_ALARM     = "#1C2840"   # Alarm panel — dark navy (NOT black)
BG_ACCENT    = "#2471A3"   # Blue accent stripe

# ── 3-D Bevel Effect ───────────────────────────────────────────────────────────
BEVEL_LIGHT  = "#F0F3F4"   # Raised top/left highlight
BEVEL_MID    = "#ADB5BD"   # Mid bevel
BEVEL_DARK   = "#7F8C8D"   # Sunken bottom/right shadow
BEVEL_DARKER = "#2C3E50"   # Deep shadow — dark slate (not black)

# ── Text ───────────────────────────────────────────────────────────────────────
TEXT_DARK    = "#1A252F"   # "Black" → deep navy
TEXT_MED     = "#4A5568"   # Medium label text
TEXT_LIGHT   = "#7F8C8D"   # Dimmed/inactive text
TEXT_WHITE   = "#FDFEFE"   # White text on dark bg
TEXT_TOPBAR  = "#D6EAF8"   # Topbar label text — pale blue-white
TEXT_ALARM   = "#BFC9CA"   # Text on alarm panel background

# ── Status / Signal LEDs ───────────────────────────────────────────────────────
STATUS_OK    = "#1E8449"   # Running / normal — forest green
STATUS_OK2   = "#27AE60"   # Bright green (LED lit)
STATUS_STOP  = "#B03A2E"   # Stopped / fault — deep red
STATUS_STOP2 = "#C0392B"   # Bright red (LED lit)
STATUS_WARN  = "#CA6F1E"   # Warning — deep amber
STATUS_WARN2 = "#E59866"   # Light amber
STATUS_UNKN  = "#7F8C8D"   # Unknown / offline — gray
STATUS_STBY  = "#1A5276"   # Standby — dark blue

# ── P&ID Color Codes (ISA-inspired) ───────────────────────────────────────────
PIPE_WATER   = "#154360"   # Raw water line — dark navy blue
PIPE_TREATED = "#145A32"   # Treated water — dark forest green
PIPE_CHEM    = "#6C3483"   # Chemical (NaOH) line — purple
PIPE_SLUDGE  = "#6E2F1A"   # Sludge — brown
PIPE_AIR     = "#7F8C8D"   # Air/gas — gray
PIPE_FILL    = "#7FB3D3"   # Water fill (lighter blue)

# ── Alarm Annunciator Tiles ────────────────────────────────────────────────────
ALM_ACTIVE   = "#B03A2E"   # Active alarm — red
ALM_ACKED    = "#CA6F1E"   # Acked/uncleared — amber
ALM_NORMAL   = "#1A5C2A"   # Normal state tile — dark green
ALM_NORMAL2  = "#27AE60"   # Normal LED indicator
ALM_TEXT_ALM = "#FDFEFE"
ALM_TEXT_NRM = "#A9DFBF"

# ── Digital Display ────────────────────────────────────────────────────────────
DISP_BG    = "#EEF2F7"   # Off-white display background
DISP_TEXT  = "#1A252F"   # Deep navy value text
DISP_UNIT  = "#566573"   # Unit label
DISP_ALRM  = "#C0392B"   # Alarm value text — red
DISP_FRAME = "#7F8C8D"   # Display frame border

# ── Fonts ──────────────────────────────────────────────────────────────────────
_SANS = "Arial"
_MONO = "Courier New"

FONT_STATUS   = (_SANS,  8)
FONT_SMALL    = (_SANS,  9)
FONT_SMALL_B  = (_SANS,  9, "bold")
FONT_LABEL    = (_SANS, 10)
FONT_LABEL_B  = (_SANS, 10, "bold")
FONT_TITLE    = (_SANS, 11, "bold")
FONT_VALUE    = (_MONO, 11, "bold")    # Digital readout
FONT_VALUE_LG = (_MONO, 15, "bold")   # Large digital readout
FONT_TOPBAR   = (_SANS, 12, "bold")
FONT_TOPBAR_S = (_SANS,  9)
FONT_BRAND    = (_SANS, 10, "bold")
FONT_ALARM    = (_SANS,  9, "bold")
FONT_DISP_LG  = (_MONO, 20, "bold")
FONT_PID      = (_SANS,  8)
FONT_PID_B    = (_SANS,  8, "bold")
FONT_MENU     = (_SANS,  9)

# ── Geometry ───────────────────────────────────────────────────────────────────
WIN_W = 1420
WIN_H = 900
