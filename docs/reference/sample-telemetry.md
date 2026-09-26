---
title: Sample Telemetry Evidence
description: Inventory the supplied CSV exports, observed units, missing values, and unresolved semantics before extending the simulator.
content-type: reference
audience: Python contributors
last-verified: 2026-09-26
---

# Sample Telemetry Evidence

This reference records source evidence inspected on September 26, 2026; it does not define an implemented channel mapping or an approved subsystem model.
See the existing [data contracts](../contracts.md) and [physics model](../physics-model.md).

## Source and Timing

The supplied `sample_telemetry_data/` directory contains 61 CSVs, `All_telemetry_samples.zip`, and `FullScreenScreenshot.PNG`; no data dictionary accompanies them.
All individual CSVs were inspected and are byte-identical to the archive entries. Archive SHA-256: `9b59153afb54e99202151c4df74399fa3cdbc02522555cc41453eb94f8676fdf`.
All source paths below are relative to `sample_telemetry_data/`.

The user confirmed **UTC** timestamps and requested **one simulated measurement per second**. Source text uses `YYYY-MM-DD HH:MM:SS` without an offset, mostly from September 1 through October 1, 2025.
The requested generation cadence is distinct from the export spacing: most panels have hourly rows; EPS panel currents use 20 minutes; payload power/opto-mechanics and solar flux use 30 minutes; ADCS one-orbit control error uses 90 minutes; FC uptime uses 2 hours; Kp uses 3 hours; FC navigation/GNSS panels use 6 hours.
EPS uptime is mostly 60–61 seconds with duplicates and longer gaps; payload memory uses an irregular joined timeline with a 3-hour grid.
Spacing does not establish source cadence or aggregation-window alignment. `.mean`, `.last`, `.mean_stddev`, mean/max/min series, fractional status values, and mapped text are evidence of processed dashboard exports.

## Inventory Counts

Fields are non-`Time` columns counted separately per CSV; rows exclude headers and retain duplicates; blanks are empty value cells.
Every CSV starts with `Time`, followed by 1–16 value columns.

| Directory | CSVs | Rows | Fields | Blanks |
|---|---:|---:|---:|---:|
| `EPS_genereal/` | 10 | 49,805 | 55 | 783 |
| `FC_general/` | 13 | 4,161 | 16 | 194 |
| `Payload/` | 8 | 6,827 | 52 | 8,857 |
| `Space_weather/` | 3 | 3,087 | 3 | 0 |
| `ADCS_general/` | 27 | 19,014 | 84 | 334 |
| **Total** | **61** | **82,894** | **210** | **10,168** |

## Exact Panel and Column Inventory

Panel/column names and column order are preserved exactly, including `EPS_genereal` spelling.
Within each directory, `single <time>` means `<panel>-data-2026-09-25 <time>.csv`; `joined <time>` means `<panel>-data-as-joinbyfield-2026-09-25 <time>.csv`.
For example: `EPS_genereal/Battery Current Flow-data-as-joinbyfield-2026-09-25 14_26_56.csv`. Filename export times differ from observation times.
Units are literal suffixes found anywhere in that export, not assignments to every column. `none` means no suffix, not a confirmed dimensionless quantity.

### EPS: `EPS_genereal/`

| Panel | Export | Rows | Value columns | Units observed |
|---|---|---:|---|---|
| Battery Current Flow | `joined 14_26_56` | 713 | `IN`, `OUT` | `A`, `mA` |
| Battery Voltage | `joined 14_26_49` | 713 | `Battery Voltage Mean`, `Battery Voltage Max`, `Battery Voltage Min` | `V` |
| GS Watch-Dog Time Left | `single 14_27_51` | 713 | `urdaneta.eps.GeneralTelemetry.mean` | `day`, `hour` |
| Power Channels' Current | `joined 14_27_34` | 713 | `AO-0`, `AO-1`, `Out 1`, `Out 2`, `Out 3`, `Out 4`, `Out 5`, `Out 6`, `Out 7`, `Out 8`, `Out 9`, `Out 10`, `Out 11`, `Out 12`, `Out 13`, `Out 14` | `A`, `mA`, `µA` |
| Solar Current | `single 14_27_04` | 713 | `Solar Current` | `A`, `mA` |
| Solar Panels Boost Converters Voltage | `joined 14_27_20` | 713 | `MPPT Converter 1`, `MPPT Converter 2`, `MPPT Converter 3`, `MPPT Converter 4` | `V`, `mV` |
| Solar Panels' Current | `joined 14_27_14` | 2,137 | `Panel 3`, `Panel 4`, `Panel 5`, `Panel 7`, `Panel 8` | `A`, `mA`, `µA` |
| Temperatures | `joined 14_27_26` | 713 | `MPPT Conv 1`, `MPPT Conv 2`, `MPPT Conv 3`, `MPPT Conv 4`, `OUT Conv 1`, `OUT Conv 2`, `OUT Conv 3`, `OUT Conv 4`, `BP 1`, `BP 2`, `BP 3`, `BP 4`, `Ext. Board 1`, `Ext. Board 2` | `°C` |
| Uptime Graph | `single 14_26_39` | 41,964 | `Uptime` | none |
| Voltages of Boost Converters for Outputs | `joined 14_27_44` | 713 | `Converter 1`, `Converter 2`, `Converter 3`, `Converter 4`, `Converter 5`, `Converter 6`, `Converter 7`, `Converter 8` | none |

### Flight Computer: `FC_general/`

| Panel | Export | Rows | Value columns | Units observed |
|---|---|---:|---|---|
| Altitude | `single 14_32_54` | 119 | `urdaneta.fc.GeneralTelemetry.mean` | `km` |
| Altitude | `single 14_33_35` | 119 | `urdaneta.fc.GeneralTelemetry.mean` | `km` |
| Ext. Temperature and Magnetic Sensors Current | `single 14_33_17` | 713 | `External Sensors Current` | `mA`, `µA` |
| Fix Quality (Graph) | `single 14_32_38` | 119 | `urdaneta.fc.GeneralTelemetry.last` | none |
| Ground Speed | `single 14_32_50` | 119 | `urdaneta.fc.GeneralTelemetry.mean` | `km/h` |
| Latitude | `single 14_32_44` | 119 | `urdaneta.fc.GeneralTelemetry.mean` | none |
| Longitude | `single 14_32_47` | 119 | `urdaneta.fc.GeneralTelemetry.mean` | none |
| MCU Temperature | `single 14_33_03` | 713 | `MCU Temperature` | `°C` |
| Magnetorquer Voltage | `single 14_32_59` | 713 | `Magnetorquer Voltage` | `V` |
| Number of Sats Tracked | `single 14_32_34` | 119 | `urdaneta.fc.GeneralTelemetry.last` | none |
| Number of Sats in View (Graph) | `single 14_32_30` | 119 | `urdaneta.fc.GeneralTelemetry.last` | none |
| Solar Panels Temperature | `joined 14_33_10` | 713 | `Solar Panel 1`, `Solar Panel 2`, `Solar Panel 4`, `Solar Panel 5` | `°C` |
| Uptime Graph | `single 14_30_50` | 357 | `Uptime` | `day`, `hour`, `week` |

### Payload: `Payload/`

| Panel | Export | Rows | Value columns | Units observed |
|---|---|---:|---|---|
| Acquisition Status | `joined 14_36_55` | 713 | `SOM2 Camera1 Status`, `SOM2 Camera2 Status`, `SOM2 Window ID`, `SOM2 Camera 1 Counter Pics`, `SOM2 Camera 2 Counter Pics` | none |
| Electronics Temperatures | `joined 14_35_56` | 713 | `SOM1_DC-DC`, `SOM1_PCB`, `SOM2_DC-DC`, `SOM2_PCB`, `SOM2_MPSoC`, `SOM2_NVME`, `TCS_DCDC`, `TCS_Heaters`, `TCS_Analog`, `TCS_MCU`, `SOM2_Xband.ad9361`, `SOM2_Xband.zynq`, `SOM2_Xband.EthPhy` | `°C` |
| File Download Status | `joined 14_36_33` | 713 | `SOM2 Files Transferred`, `SOM2 Bytes Transferred` | none, `GB`, `MB`, `kB` |
| Memory Usage | `joined 14_37_07` | 412 | `NOR telemetry`, `NOR log`, `SOM2 NVMe` | `%` |
| Opto-mechanics Temperatures | `joined 14_36_44` | 1,425 | `TC1_FP_Center`, `TC2_FP_Right`, `TC3_FP_Left`, `TC4_RP_Center`, `TC5_RP_Left`, `TC6_RP_Right`, `OneWire 1_Left`, `OneWire 1_Right` | `°C` |
| Power | `joined 14_36_19` | 1,425 | `Spock_Vin`, `Spock_3.3V_SPV`, `Spock_6V_SPV`, `Spock_12V_SOM1`, `Spock_3.3V_NVME_1`, `Spock_12V_SOM2`, `Spock_3.3V_NVME_2`, `Spock_12V_CAM1`, `Spock_12V_CAM2`, `Spock_Vin_TCS`, `SmartHeater_Vin`, `SmartHeater_Heaters` | `W`, `mW`, `nW`, `µW` |
| Smartheater PWM | `joined 14_36_26` | 713 | `Heater 1 FP_Center`, `Heater 2 FP_Right`, `Heater 3 FP_Left`, `Heater 4 RP_Center`, `Heater 5 RP_Left`, `Heater 6 RP_Right` | `%` |
| Uptimes | `joined 14_36_01` | 713 | `SPV`, `TCS`, `SOM2` | `hour`, `min`, `s` |

### Space Weather: `Space_weather/`

| Panel | Export | Rows | Value columns | Units observed |
|---|---|---:|---|---|
| Geomagnetic Activity | `single 14_29_16` | 237 | `Kp Index` | none |
| Solar Proton Flux (integral) | `single 14_29_21` | 1,425 | `>=10MeV` | none |
| Solar X-Ray Flux | `single 14_29_10` | 1,425 | `GOES-16 long` | none |

### ADCS: `ADCS_general/`

| Panel | Export | Rows | Value columns | Units observed |
|---|---|---:|---|---|
| Angular Velocity | `joined 14_05_59` | 713 | `W_BCF_X`, `W_BCF_Y`, `W_BCF_Z` | `deg/s` |
| Attitude Determination Mode | `joined 14_05_37` | 713 | `Requested`, `Selected` | none |
| Control Error for 1 Orbit (1 Sigma) | `single 14_06_50` | 476 | `urdaneta.fc.AdcsTelemetry.mean_stddev` | none |
| Control Error per Axis | `joined 14_03_53` | 713 | `X`, `Y`, `Z` | none |
| Control Error | `joined 14_03_45` | 713 | `All values`, `<5 deg` | `°` |
| Controller mode (pointing mode) | `single 14_06_59` | 713 | `urdaneta.fc.AdcsTelemetry.mean` | none |
| Demanding Torque | `joined 14_04_44` | 713 | `Torque-X`, `Torque-Y`, `Torque-Z` | none |
| Gyro Individual Vectors | `joined 14_06_36` | 713 | `Gyro 1 Vector 0`, `Gyro 2 Vector 0`, `Gyro 1 Vector 1`, `Gyro 2 Vector 1`, `Gyro 1 Vector 2`, `Gyro 2 Vector 2`, `Gyro 3 Vector 0`, `Gyro 3 Vector 1`, `Gyro 3 Vector 2` | `deg/s` |
| Gyro United | `joined 14_06_11` | 713 | `Gyro United X`, `Gyro United Y`, `Gyro United Z` | `deg/s` |
| IMU (Gyroscope) | `joined 14_06_26` | 713 | `IMU X`, `IMU Y`, `IMU Z` | `deg/s` |
| Knowledge Quaternion | `joined 14_04_57` | 713 | `Quat 1`, `Quat 2`, `Quat 3`, `Quat 4` | none |
| Magnetometer Measurement United | `joined 14_04_19` | 713 | `MagVectorUnited X`, `MagVectorUnited Y`, `MagVectorUnited Z` | `Tesla` |
| Magnetorquer Activation Signal | `joined 14_05_28` | 713 | `MTQ Activation 1`, `MTQ Activation 2`, `MTQ Activation 3` | none |
| Off-Nadir Angle | `joined 14_04_04` | 713 | `X`, `Y`, `Z` | `°` |
| Pointing Target | `single 14_01_59` | 713 | `urdaneta.fc.AdcsTelemetry.mean` | none |
| RW Pressure | `joined 14_07_06` | 713 | `RW1b`, `RW2b`, `RW3b`, `RW4b` | `mbar` |
| RW Temperature | `joined 14_05_43` | 713 | `RW1_MCU_Temperature`, `RW2_MCU_Temperature`, `RW3_MCU_Temperature`, `RW4_MCU_Temperature` | `°C` |
| Reaction Wheels Speed | `joined 14_04_11` | 713 | `RW1`, `RW2`, `RW3`, `RW4` | `RPM` |
| Reaction Wheels Speed | `joined 14_05_22` | 713 | `RW1`, `RW2`, `RW3`, `RW4` | none; mapped text |
| Reset on Control Error Low Pass Filter Error | `single 14_04_29` | 713 | `urdaneta.fc.AdcsTelemetry.mean` | `°` |
| Sat Position ECI | `joined 14_07_19` | 713 | `Position_x`, `Position_y`, `Position_z` | none |
| Star Tracker 1 - Quaternion | `joined 14_05_03` | 713 | `Q - R`, `Q - X`, `Q - Y`, `Q - Z` | none |
| Star Tracker 2 - Quaternion | `joined 14_05_09` | 713 | `Q - R`, `Q - X`, `Q - Y`, `Q - Z` | none |
| Star Tracker Temperature | `joined 14_04_37` | 713 | `STQ2`, `STQ1` | `°C` |
| Sun Sensors United | `joined 14_05_52` | 713 | `SunVectorUnited X`, `SunVectorUnited Y`, `SunVectorUnited Z` | none |
| Target Quaternion | `joined 14_04_51` | 713 | `Target Quat 1`, `Target Quat 2`, `Target Quat 3`, `Target Quat 4` | none |
| [Auriga] STQ Quality | `joined 14_05_15` | 713 | `STQ Quality`, `STQ1`, `STQ2` | hex strings; no suffix |

## Values and Missing Data

| Observed column representation | Fields | Evidence |
|---|---:|---|
| Numeric with explicit suffixes | 144 | Examples: `1.05 A`, `497 mA`, `74.1 µA`, `8.265 V`, `80.07%`, `-5.52 °C` |
| Numeric without suffixes | 59 | Includes modes, quaternion components, ECI coordinates, counts, and raw converter values |
| Hexadecimal strings | 3 | `[Auriga] STQ Quality` columns contain `0x0`, `0xCC`, and other codes |
| Mapped text only | 2 | Reaction Wheels Speed `14_05_22`: `RW1` and `RW4` contain only `Zero Crossings - Unstability` |
| Numbers and mapped text | 2 | The same export's `RW2` and `RW3` also contain bare numbers |

Prefixes change within columns: `A`/`mA`/`µA`, `V`/`mV`, and `W`/`mW`/`µW`/`nW`. Other explicit suffixes are `°C`, `s`, `min`, `hour`, `day`, `week`, `km`, `km/h`, `°`, `deg/s`, `Tesla`, `RPM`, `mbar`, `%`, `kB`, `MB`, and `GB`.
`SOM2 Bytes Transferred` uses storage suffixes; `SOM2 Files Transferred` has none. Decimal-versus-binary storage formatting is unspecified. Some small power readings are negative, such as `-662 nW`, without an explanation in the source.

Empty cells do not distinguish inactive hardware, missing downlinks, invalid readings, unsupported channels, or unavailable aggregates; they are distinct from numeric zeros.
Payload acquisition-status and file-download-status columns each have only 149 nonblank records out of 713. Camera-status and files-transferred columns include fractional values, so their labels do not establish raw integer status/counter types.

## Duplicates and Overlaps

| Source | Observed evidence |
|---|---|
| EPS Uptime Graph | 161 timestamps each occur twice, giving 161 extra rows; every repeated timestamp has an identical complete row. |
| FC Altitude | Exports `14_32_54` and `14_33_35` share headers and 119 rows, but four timestamped values differ. |
| ADCS Reaction Wheels Speed | Both exports use `RW1`–`RW4`; `14_04_11` contains RPM, while `14_05_22` contains mapped text and some bare numbers. |
| ADCS Control Error per Axis / Off-Nadir Angle | All three numeric series are identical after removing the latter's `°` suffixes; the differing panel names are unexplained. |

Panel title and column label alone do not identify every export. These observations do not establish a merging or deduplication policy.

## Screenshot Evidence and Unresolved Semantics

`FullScreenScreenshot.PNG` shows Grafana, satellite/payload views, and ground-station plots. Grafana explicitly displays UTC for October 21–25, 2025, a different interval from the CSVs.
Bus/ADCS selectors show `urdaneta`; payload/ground-station selectors show `ARMSAT1`. Their identity relationship is not stated.
The output-converter chart displays volts, but its CSV has bare values such as `3341`, `5008`, and `11985`; no explicit conversion is supplied. Ground-station link measurements and EPS fault counters visible in the screenshot lack corresponding CSVs.

The sources do not supply aggregation queries/window alignment, quality/missingness semantics, packet sequences, or a mission/source identity mapping.
Units/calibration remain unspecified for bare converter readings, torque, magnetorquer activation, ECI coordinates, and flux values; current-flow direction and the circuit relationship among electrical channels are undefined.
ECI realization, vector frames, quaternion ordering/reference direction, and dictionaries for target/mode, GNSS fix, camera status, and star-tracker bitmask codes are absent.
Knowledge-quaternion norms range approximately 0.044–0.961; this describes exported values, not a usable attitude convention or proof of a particular averaging method.
Model extensions and synthetic approximations require decisions separate from this evidence record.
