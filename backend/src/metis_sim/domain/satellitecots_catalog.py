"""Source-specific channel meanings for BUPT-1's published telemetry table."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from metis_sim.domain.catalog import ChannelDefinition

SATELLITECOTS_CATALOG_VERSION = "satellitecots.v1"

# Ordered exactly as telemetry_all.csv. Electrical source values are mV/mA;
# temperatures are degrees Celsius. Cadence describes the paper's acquisition
# intervals, not fresh measurements of every sensor on each merged CSV row.
SOURCE_CHANNELS: dict[str, tuple[str, str, float, int, str]] = {
    "Total_I": ("eps.bus_current_a", "A", 0.001, 1, "Total spacecraft bus current"),
    "Total_U": ("eps.bus_voltage_v", "V", 0.001, 1, "Total spacecraft bus voltage"),
    "MPPT1_Uin": ("eps.mppt_1_input_voltage_v", "V", 0.001, 3, "MPPT 1 input voltage"),
    "MPPT1_Iin": ("eps.mppt_1_input_current_a", "A", 0.001, 3, "MPPT 1 input current"),
    "MPPT1_Iout": ("eps.mppt_1_output_current_a", "A", 0.001, 3, "MPPT 1 output current"),
    "MPPT2_Uin": ("eps.mppt_2_input_voltage_v", "V", 0.001, 3, "MPPT 2 input voltage"),
    "MPPT2_Iin": ("eps.mppt_2_input_current_a", "A", 0.001, 3, "MPPT 2 input current"),
    "MPPT2_Iout": ("eps.mppt_2_output_current_a", "A", 0.001, 3, "MPPT 2 output current"),
    "BATTERY1_U": ("eps.battery_1_voltage_v", "V", 0.001, 4, "Battery 1 voltage"),
    "BATTERY1_I": ("eps.battery_1_current_a", "A", 0.001, 4, "Battery 1 signed source current"),
    "BATTERY2_U": ("eps.battery_2_voltage_v", "V", 0.001, 4, "Battery 2 voltage"),
    "BATTERY2_I": ("eps.battery_2_current_a", "A", 0.001, 4, "Battery 2 signed source current"),
    "UV_U_3V3": ("comm.uv_voltage_v", "V", 0.001, 1, "U/V communications rail voltage"),
    "UV_I": ("comm.uv_current_a", "A", 0.001, 1, "U/V communications current"),
    "POBC_I_5V": ("fc.pobc_current_a", "A", 0.001, 1, "Payload onboard computer current"),
    "XMIT_A_12V": ("comm.transmitter_a_current_a", "A", 0.001, 1, "Baseband A current"),
    "XMIT_B_12V": ("comm.transmitter_b_current_a", "A", 0.001, 1, "Baseband B current"),
    "I_Atlas200DK-A": ("payload.atlas_a_current_a", "A", 0.001, 1, "Atlas 200 DK A current"),
    "I_Atlas200DK-B": ("payload.atlas_b_current_a", "A", 0.001, 1, "Atlas 200 DK B current"),
    "I_Pi-A": ("payload.pi_a_current_a", "A", 0.001, 1, "Raspberry Pi 4B A current"),
    "I_Pi-B": ("payload.pi_b_current_a", "A", 0.001, 1, "Raspberry Pi 4B B current"),
    "ATLAS_A_TEMP": (
        "payload.atlas_a_temperature_c",
        "degC",
        1.0,
        4,
        "Atlas A surface temperature",
    ),
    "ATLAS_B_TEMP": (
        "payload.atlas_b_temperature_c",
        "degC",
        1.0,
        4,
        "Atlas B surface temperature",
    ),
    "PI_A_TEMP": (
        "payload.pi_a_temperature_c",
        "degC",
        1.0,
        4,
        "Raspberry Pi A surface temperature",
    ),
}
SOURCE_COLUMNS = tuple(SOURCE_CHANNELS)


def satellitecots_channels() -> tuple[ChannelDefinition, ...]:
    """Describe recorded sensors and reproducible source-derived power channels.

    Returns
    -------
    tuple of ChannelDefinition
        All 24 source fields in SI units, plus three electrical derivations.
        Original zero values are retained; the source does not document a
        universal zero-as-missing convention. No orbit, SOC, operating mode,
        battery topology, or thermal aggregation is inferred.
    """
    from metis_sim.domain.catalog import ChannelDefinition

    sensors = tuple(
        ChannelDefinition(
            channel_id,
            unit,
            "scalar",
            "sensor",
            "endpoint",
            None,
            None,
            cadence,
            f"{description}, recorded BUPT-1 source field {column}. "
            "Unit conversion only; the merged table may repeat slower sensor readings.",
            "observed",
        )
        for column, (channel_id, unit, _, cadence, description) in SOURCE_CHANNELS.items()
    )
    derived = (
        (
            "eps.solar_power_w",
            "W",
            3,
            "(MPPT1_Iout + MPPT2_Iout) * Total_U / 1e6, following the upstream Energy-Overview recipe. "
            "Snapshot-derived bus delivery power, not a one-second interval mean.",
        ),
        (
            "eps.load_served_w",
            "W",
            1,
            "Total_I * Total_U / 1e6, following upstream total spacecraft consumption. "
            "Snapshot-derived power; no requested or unserved load is inferred.",
        ),
        (
            "eps.solar_current_a",
            "A",
            3,
            "(MPPT1_Iout + MPPT2_Iout) / 1000, the sum of recorded MPPT output currents.",
        ),
    )
    return sensors + tuple(
        ChannelDefinition(
            name,
            unit,
            "scalar",
            "derived",
            "endpoint",
            None,
            None,
            cadence,
            description,
            "observed",
        )
        for name, unit, cadence, description in derived
    )
