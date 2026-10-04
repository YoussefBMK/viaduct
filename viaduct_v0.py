"""Viaduct V0 -- ESP32-S3 + BME280 environmental sensor board, described in SKiDL.

USB-C 5 V in -> AP2112K-3.3 LDO -> 3V3 rail -> ESP32-S3-WROOM-1 module, with a
BME280 on I2C and native USB (no USB-to-serial bridge) protected by a USBLC6-2.

Every part below is a stock KiCad 10 symbol with a stock KiCad 10 footprint;
nothing is invented. Run `python viaduct_v0.py` to emit `viaduct_v0.net`.

Datasheets cited in the comments
-------------------------------
[ESP]   ESP32-S3-WROOM-1 & ESP32-S3-WROOM-1U Datasheet v1.8, Espressif
        https://www.espressif.com/sites/default/files/documentation/esp32-s3-wroom-1_wroom-1u_datasheet_en.pdf
[BME]   BME280 Datasheet BST-BME280-DS001-23, Revision 1.23, 01/2022, Bosch Sensortec
        https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bme280-ds002.pdf
[AP]    AP2112 Datasheet DS39724 Rev. 2-2, June 2017, Diodes Incorporated
        https://www.diodes.com/assets/Datasheets/AP2112.pdf
[LC6]   USBLC6-2 Datasheet DS4260 Rev 7, December 2021, STMicroelectronics
        https://www.st.com/resource/en/datasheet/usblc6-2.pdf

Section/page numbers refer to those exact revisions; they were read out of the
PDFs, not recalled.
"""

import builtins
import os

# SKiDL finds KiCad symbol libraries only through KICAD<n>_SYMBOL_DIR, and it
# reads the variable at import time. Setting it here keeps the script
# self-contained -- no shell setup needed before running it.
os.environ.setdefault("KICAD10_SYMBOL_DIR", "/usr/share/kicad/symbols")

from skidl import (  # noqa: E402
    ERC,
    KICAD10,
    POWER,
    Net,
    Part,
    generate_netlist,
    set_default_tool,
)

# SKiDL 2.3.0 injects the no-connect net into `builtins` on import instead of
# exporting it from the package, so `from skidl import NC` raises ImportError.
# Pulling it off builtins explicitly avoids `from skidl import *`.
NC = builtins.NC

set_default_tool(KICAD10)

# --------------------------------------------------------------------------
# Nets
# --------------------------------------------------------------------------
# drive=POWER marks these as driven rails so ERC does not report them as nets
# with no driver -- the real driver is off-board (the USB host) or the LDO.
gnd = Net("GND", drive=POWER)
vbus = Net("VBUS", drive=POWER)  # 5 V from USB-C
v3v3 = Net("+3V3", drive=POWER)  # LDO output

# USB data, connector side and module side, separated by the ESD array.
usb_dp_con = Net("USB_D+_CON")
usb_dm_con = Net("USB_D-_CON")
usb_dp = Net("USB_D+")
usb_dm = Net("USB_D-")

en = Net("EN")  # ESP32-S3 chip-enable / reset
boot = Net("BOOT")  # GPIO0, boot-mode strap
sda = Net("I2C_SDA")
scl = Net("I2C_SCL")
cc1 = Net("CC1")
cc2 = Net("CC2")
led_a = Net("LED_A")

# --------------------------------------------------------------------------
# J1 -- USB-C receptacle, USB 2.0, 16 position
# --------------------------------------------------------------------------
# Symbol Connector:USB_C_Receptacle_USB2.0_16P carries no footprint field, so
# one is assigned explicitly. All 17 symbol pins have a matching pad in the
# GCT USB4105 footprint (checked pad-by-pad against the .kicad_mod).
j1 = Part(
    "Connector",
    "USB_C_Receptacle_USB2.0_16P",
    ref="J1", tag="J1",
    value="USB-C",
    footprint="Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal",
)

# The receptacle duplicates every power/data contact across the two rows so the
# cable works in either orientation; both halves of each pair are tied together.
j1["A1", "B1", "A12", "B12"] += gnd  # GND contacts
j1["A4", "B4", "A9", "B9"] += vbus  # VBUS contacts
j1["A6", "B6"] += usb_dp_con  # D+ contacts
j1["A7", "B7"] += usb_dm_con  # D- contacts

# Shield to GND: this board has a single ground, so chassis and signal ground
# are the same net.
j1["SH"] += gnd

# SBU1/SBU2 are only used by alternate modes (DisplayPort, audio accessory).
# This board implements none of them, so they are deliberately left open.
j1["A8", "B8"] += NC

# CC pull-downs. A USB-C *source* decides whether to turn VBUS on by sensing
# Rd on CC; with CC floating it sees no sink and never supplies 5 V. Both CC1
# and CC2 need one because only the contact that happens to mate with the
# cable's CC wire is active -- which one depends on plug orientation.
# Rd = 5.1 kohm is the value fixed by the USB Type-C Cable and Connector
# Specification. NOTE: that specification was not read for this build; 5.1 k
# is carried over from the design brief. See "unverified" in the report.
r_cc1 = Part("Device", "R", ref="R1", tag="R1", value="5.1k",
             footprint="Resistor_SMD:R_0603_1608Metric")
r_cc2 = Part("Device", "R", ref="R2", tag="R2", value="5.1k",
             footprint="Resistor_SMD:R_0603_1608Metric")
j1["A5"] += cc1
r_cc1[1] += cc1
r_cc1[2] += gnd
j1["B5"] += cc2
r_cc2[1] += cc2
r_cc2[2] += gnd

# --------------------------------------------------------------------------
# U1 -- USBLC6-2SC6 ESD protection on the USB data pair
# --------------------------------------------------------------------------
# Pin assignment from [LC6] p.1 "Functional diagram (top view)":
#   1 I/O1   2 GND   3 I/O2   4 I/O2   5 VBUS   6 I/O1
# Each I/O pair (1-6 and 3-4) is one protected line passed through the device,
# so the data signal enters on one pin of a pair and leaves on the other.
u1 = Part(
    "Power_Protection",
    "USBLC6-2SC6",
    ref="U1", tag="U1",
    value="USBLC6-2SC6",
    footprint="Package_TO_SOT_SMD:SOT-666",
)
u1[1] += usb_dm_con  # I/O1, connector side
u1[6] += usb_dm  # I/O1, module side
u1[3] += usb_dp_con  # I/O2, connector side
u1[4] += usb_dp  # I/O2, module side
u1[2] += gnd  # GND
u1[5] += vbus  # VBUS -- [LC6] p.1 Features, "Protects VBUS"

# --------------------------------------------------------------------------
# U2 -- AP2112K-3.3 LDO, 5 V -> 3.3 V
# --------------------------------------------------------------------------
# Pin assignment from [AP] p.2 "Pin Descriptions", SOT25 column:
#   1 VIN   2 GND   3 EN   4 NC   5 VOUT
u2 = Part(
    "Regulator_Linear",
    "AP2112K-3.3",
    ref="U2", tag="U2",
    value="AP2112K-3.3",
    footprint="Package_TO_SOT_SMD:SOT-23-5",
)
u2[1] += vbus  # VIN -- "Input Voltage"
u2[2] += gnd  # GND
u2[5] += v3v3  # VOUT -- "Output Voltage"

# EN tied to VIN keeps the regulator permanently on: [AP] p.2 describes EN as
# "Chip Enable, H - normal work, L - shutdown output". There is no sequencing
# requirement on this board, so EN follows VBUS.
u2[3] += vbus

# Pin 4 is "NC - No Connection" per the same table.
u2[4] += NC

# Input and output capacitors straight from [AP] p.2 "Typical Applications
# Circuit": CIN = 1 uF, COUT = 1 uF. Note 4 of that figure: "It is recommended
# to use X7R or X5R dielectric capacitor if 1.0 uF ceramic capacitor is
# selected as input/output capacitors."
c_in = Part("Device", "C", ref="C1", tag="C1", value="1uF X5R",
            footprint="Capacitor_SMD:C_0603_1608Metric")
c_out = Part("Device", "C", ref="C2", tag="C2", value="1uF X5R",
             footprint="Capacitor_SMD:C_0603_1608Metric")
c_in[1] += vbus
c_in[2] += gnd
c_out[1] += v3v3
c_out[2] += gnd

# Current budget. [ESP] Table 6-2 "Recommended Operating Conditions" (p.27)
# gives I_VDD, "Current delivered by external power supply", Min = 0.5 A.
# [ESP] Table 6-4 (p.28) gives the worst-case RF peak as 355 mA (802.11b,
# 1 Mbps, @20.5 dBm TX); Table 6-5 gives 344 mA for Bluetooth LE @20 dBm.
# [AP] p.1 Features: "Output Current: 600mA (Min.)". 600 mA clears both the
# 500 mA floor and the 355 mA peak, leaving ~245 mA for the sensor and LED
# (both well under 10 mA). The margin over the datasheet floor is 20%.

# --------------------------------------------------------------------------
# U3 -- ESP32-S3-WROOM-1
# --------------------------------------------------------------------------
# Pin numbers below are the "No." column of [ESP] Table 3-1 Pin Definitions
# (p.11-12), which is also how the KiCad symbol numbers its pins.
u3 = Part(
    "RF_Module",
    "ESP32-S3-WROOM-1",
    ref="U3", tag="U3",
    value="ESP32-S3-WROOM-1",
    footprint="RF_Module:ESP32-S3-WROOM-1",
)

u3[1] += gnd  # pin 1  GND
u3[40] += gnd  # pin 40 GND
u3[41] += gnd  # pin 41 EPAD -- type P, "GND" in Table 3-1. The note under
#                 Figure 9-1 says soldering the EPAD is not mandatory but
#                 "can optimize thermal performance", so it is connected.
u3[2] += v3v3  # pin 2  3V3, "Power supply"

# 3V3 decoupling copied from [ESP] Figure 9-1 Peripheral Schematics (p.41),
# which shows exactly two capacitors on the VDD33 rail: C1 = 22 uF bulk and
# C3 = 0.1 uF high-frequency.
c_bulk = Part("Device", "C", ref="C3", tag="C3", value="22uF X5R",
              footprint="Capacitor_SMD:C_0603_1608Metric")
c_hf = Part("Device", "C", ref="C4", tag="C4", value="100nF X7R",
            footprint="Capacitor_SMD:C_0603_1608Metric")
c_bulk[1] += v3v3
c_bulk[2] += gnd
c_hf[1] += v3v3
c_hf[2] += gnd

# ---- EN (pin 3) ----
# [ESP] Table 3-1: "High: on, enables the chip. Low: off, the chip powers off.
# Note: Do not leave the EN pin floating." -- hence the pull-up.
# The note under Figure 9-1 (p.41): "To ensure that the power supply to the
# ESP32-S3 chip is stable during power-up, it is advised to add an RC delay
# circuit at the EN pin. The recommended setting for the RC delay circuit is
# usually R = 10 kohm and C = 1 uF." Figure 9-1 draws this as R1 from VDD33 to
# EN and C2 from EN to GND, which is what is built here.
u3[3] += en
r_en = Part("Device", "R", ref="R3", tag="R3", value="10k",
            footprint="Resistor_SMD:R_0603_1608Metric")
c_en = Part("Device", "C", ref="C5", tag="C5", value="1uF X5R",
            footprint="Capacitor_SMD:C_0603_1608Metric")
r_en[1] += v3v3
r_en[2] += en
c_en[1] += en
c_en[2] += gnd

# Reset button: shorting EN to GND drops the chip into reset; releasing it lets
# the RC bring EN back up. Figure 9-1 shows the same button (SW1) on EN.
sw_rst = Part("Switch", "SW_Push", ref="SW1", tag="SW1", value="RESET",
              footprint="Button_Switch_SMD:SW_Push_1P1T_NO_CK_KMR2")
sw_rst[1] += en
sw_rst[2] += gnd

# ---- GPIO0 (pin 27) -- boot-mode strap ----
# [ESP] section 4 (p.13): chip boot mode is strapped by GPIO0 and GPIO46.
# Table 4-3 Chip Boot Mode Control (p.14):
#     SPI Boot            GPIO0 = 1, GPIO46 = any value   <- default
#     Joint Download Boot GPIO0 = 0, GPIO46 = 0
# Table 4-1 (p.13) gives GPIO0's default as "Weak pull-up", bit value 1, so the
# module boots from flash on its own. The external 10 k pull-up makes that
# level deterministic rather than relying on the internal weak pull-up, and the
# button pulls GPIO0 to 0 to enter download boot.
u3[27] += boot
r_boot = Part("Device", "R", ref="R4", tag="R4", value="10k",
              footprint="Resistor_SMD:R_0603_1608Metric")
r_boot[1] += v3v3
r_boot[2] += boot
sw_boot = Part("Switch", "SW_Push", ref="SW2", tag="SW2", value="BOOT",
               footprint="Button_Switch_SMD:SW_Push_1P1T_NO_CK_KMR2")
sw_boot[1] += boot
sw_boot[2] += gnd

# ---- Native USB (pins 13, 14) ----
# [ESP] Table 3-1: pin 13 = IO19, whose bolded default function is USB_D-, and
# pin 14 = IO20, default USB_D+. Using these is what removes the need for a
# USB-to-serial bridge: the ESP32-S3 has a built-in USB Serial/JTAG controller
# ([ESP] section 5.2.1.8).
u3[13] += usb_dm  # USB_D-
u3[14] += usb_dp  # USB_D+

# ---- I2C (pins 12, 17) ----
# Choice of GPIO8 / GPIO9, and why every other candidate was ruled out:
#   * GPIO0, GPIO3, GPIO45, GPIO46 are the four strapping pins ([ESP] p.13).
#     Hanging an I2C bus with pull-ups off one would change the level sampled
#     at reset and could flip boot mode or VDD_SPI voltage.
#   * GPIO19/GPIO20 (pins 13/14) are the native USB pair, used above.
#   * GPIO26-32 are the chip's SPI flash bus and are not brought out to module
#     pins at all.
#   * GPIO35, GPIO36, GPIO37 (pins 28-30) are unusable on Octal-PSRAM parts --
#     [ESP] Table 3-1 footnote b: "For modules with Octal SPI PSRAM, i.e.,
#     modules embedded with ESP32-S3R8 or ESP32-S3R16V, pins IO35, IO36, and
#     IO37 are connected to the Octal SPI PSRAM and are not available for other
#     uses." Avoiding them keeps the board valid across the whole WROOM-1 range.
#   * GPIO47/GPIO48 (pins 24/25) run at 1.8 V on the R16V variant -- footnote c
#     of the same table -- so they are not safe for a 3.3 V bus on every part.
#   * GPIO43/GPIO44 (pins 37/36, TXD0/RXD0) are the ROM bootloader's UART0.
#   * GPIO39-42 (pins 32-35) are the default JTAG pins MTCK/MTDO/MTDI/MTMS.
# What is left of GPIO8 and GPIO9 in Table 3-1 is:
#     IO8 pin 12: RTC_GPIO8, GPIO8, TOUCH8, ADC1_CH7, SUBSPICS1
#     IO9 pin 17: RTC_GPIO9, GPIO9, TOUCH9, ADC1_CH8, FSPIHD, SUBSPIHD
# Neither has a boot-time role, neither is tied to flash or PSRAM, and the ESP32
# I2C controller is routed through the GPIO matrix, so any free GPIO works.
u3[12] += sda  # IO8  -> SDA
u3[17] += scl  # IO9  -> SCL

# ---- Strapping pins left at their default ----
# [ESP] Table 4-1 Default Configuration of Strapping Pins (p.13):
#     GPIO0   Weak pull-up    bit 1
#     GPIO3   Floating        -
#     GPIO45  Weak pull-down  bit 0
#     GPIO46  Weak pull-down  bit 0
# and p.13: "The default values of the strapping pins ... are determined by
# pins' internal weak pull-up/pull-down resistors at reset if the pins are not
# connected to any circuit". Leaving them open is therefore a positive choice,
# not an omission:
#   GPIO3  (pin 15) floating -> JTAG source selected by eFuse, which is the
#          intended behaviour when USB-JTAG is used.
#   GPIO45 (pin 26) pulls down -> VDD_SPI = 3.3 V, correct for the non-R16V
#          flash/PSRAM fitted to this module.
#   GPIO46 (pin 16) pulls down -> 0, which Table 4-3 requires for Joint
#          Download Boot, so holding BOOT alone is enough to enter the
#          bootloader. It also leaves ROM message printing enabled.
# GPIO0 is the exception: it gets an explicit pull-up and a button, above.
for pin in (
    4, 5, 6, 7, 8, 9, 10, 11,  # IO4 IO5 IO6 IO7 IO15 IO16 IO17 IO18
    15, 16,                    # IO3 IO46  -- strapping, left floating on purpose
    18, 19, 20, 21, 22, 23,    # IO10 IO11 IO12 IO13 IO14 IO21
    24, 25, 26,                # IO47 IO48 IO45
    28, 29, 30, 31,            # IO35 IO36 IO37 IO38
    32, 33, 34, 35,            # IO39 IO40 IO41 IO42 (JTAG)
    36, 37,                    # RXD0 TXD0 (UART0)
    38, 39,                    # IO2 IO1
):
    u3[pin] += NC

# --------------------------------------------------------------------------
# U4 -- BME280 humidity / pressure / temperature sensor
# --------------------------------------------------------------------------
# Pin assignment from [BME] Figure 17 (p.39) and the block diagram in section
# 3.1 (p.14):
#   1 GND   2 CSB   3 SDI   4 SCK   5 SDO   6 VDDIO   7 GND   8 VDD
u4 = Part(
    "Sensor",
    "BME280",
    ref="U4", tag="U4",
    value="BME280",
    footprint="Package_LGA:Bosch_LGA-8_2.5x2.5mm_P0.65mm_ClockwisePinNumbering",
)
u4[1] += gnd  # GND
u4[7] += gnd  # GND

# [BME] section 3.2 Power management (p.14): "VDD is the main power supply for
# all internal analog and digital functional blocks"; "VDDIO is a separate
# power supply pin used for the supply of the digital interface". Both are run
# from the same 3V3 rail here, which also keeps the interface pins at the same
# level as the ESP32-S3.
u4[8] += v3v3  # VDD
u4[6] += v3v3  # VDDIO

# CSB -> VDDIO selects I2C. [BME] section 6.1 Interface selection (p.32):
# "Interface selection is done automatically based on CSB (chip select) status.
# If CSB is connected to VDDIO, the I2C interface is active. If CSB is pulled
# down, the SPI interface is activated." Figure 17's notes add: "A direct
# connection between CSB and VDDIO is required."
u4[2] += v3v3  # CSB

# SDO -> GND sets the address. [BME] section 6.2 (p.32): "The 7-bit device
# address is 111011x. ... Connecting SDO to GND results in slave address
# 1110110 (0x76); connection it to VDDIO results in slave address 1110111
# (0x77)". SDO must not float -- in I2C mode it is purely an address strap.
u4[5] += gnd  # SDO -> 0x76

# In I2C mode Figure 17 relabels SDI as SDA and SCK as SCL.
u4[3] += sda  # SDI / SDA
u4[4] += scl  # SCK / SCL

# Supply decoupling. [BME] Figure 17 notes (p.39): "The recommended value for
# C1, C2 is 100 nF" -- one on VDD, one on VDDIO.
c_vdd = Part("Device", "C", ref="C6", tag="C6", value="100nF X7R",
             footprint="Capacitor_SMD:C_0603_1608Metric")
c_vddio = Part("Device", "C", ref="C7", tag="C7", value="100nF X7R",
               footprint="Capacitor_SMD:C_0603_1608Metric")
c_vdd[1] += v3v3
c_vdd[2] += gnd
c_vddio[1] += v3v3
c_vddio[2] += gnd

# I2C bus pull-ups. [BME] Figure 17 notes (p.39): "The value for the pull-up
# resistors R1, R2 should be based on the interface timing and the bus load; a
# normal value is 4.7 kohm." The BME280 is the only device on the bus, so the
# nominal value applies.
r_sda = Part("Device", "R", ref="R5", tag="R5", value="4.7k",
             footprint="Resistor_SMD:R_0603_1608Metric")
r_scl = Part("Device", "R", ref="R6", tag="R6", value="4.7k",
             footprint="Resistor_SMD:R_0603_1608Metric")
r_sda[1] += v3v3
r_sda[2] += sda
r_scl[1] += v3v3
r_scl[2] += scl

# --------------------------------------------------------------------------
# D1 -- power-on indicator
# --------------------------------------------------------------------------
# Device:LED pin 1 = K (cathode), pin 2 = A (anode).
# R7 is an engineering choice, not a datasheet value: Device:LED is a generic
# symbol with no forward voltage attached. 1 kohm gives roughly (3.3 - 2.0)/1k
# = 1.3 mA for a typical 2.0 V red LED -- visible, and small against the
# current budget above. Re-pick it once a real LED part number is chosen.
d1 = Part("Device", "LED", ref="D1", tag="D1", value="PWR",
          footprint="LED_SMD:LED_0603_1608Metric")
r_led = Part("Device", "R", ref="R7", tag="R7", value="1k",
             footprint="Resistor_SMD:R_0603_1608Metric")
r_led[1] += v3v3
r_led[2] += led_a
d1[2] += led_a  # A
d1[1] += gnd  # K

# --------------------------------------------------------------------------
# Checks and output
# --------------------------------------------------------------------------
if __name__ == "__main__":
    ERC()
    generate_netlist(file_="viaduct_v0.net")
