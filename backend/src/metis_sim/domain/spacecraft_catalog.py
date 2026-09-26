"""Public channels for the explicitly modeled spacecraft subsystems."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from metis_sim.domain.catalog import ChannelDefinition


def spacecraft_channels() -> tuple[ChannelDefinition, ...]:
    """Describe modeled measurements and explicitly unavailable mission quantities.

    Returns
    -------
    tuple of ChannelDefinition
        Additional channels in ``spacecraft.v1``. Units describe the new
        physical models, not an inferred interpretation of the CSV exports.
    """
    from metis_sim.domain.catalog import ChannelDefinition

    scalar: list[tuple[str, str, Literal["endpoint", "interval_mean"], str]] = [
        (
            "eps.battery_voltage_v",
            "V",
            "interval_mean",
            "Equivalent regulated battery terminal voltage associated with the interval power allocation; zero for an empty inactive store. No voltage sag or electrochemistry.",
        ),
        (
            "eps.battery_current_in_a",
            "A",
            "interval_mean",
            "Positive charge current at the ideal battery terminal, after charge efficiency.",
        ),
        (
            "eps.battery_current_out_a",
            "A",
            "interval_mean",
            "Positive discharge current at the ideal battery terminal, before discharge efficiency.",
        ),
        (
            "eps.solar_voltage_v",
            "V",
            "interval_mean",
            "Equivalent regulated solar branch voltage associated with the interval power allocation; zero when generation is zero.",
        ),
        (
            "eps.solar_current_a",
            "A",
            "interval_mean",
            "Generated bus power divided by the regulated solar voltage.",
        ),
        (
            "eps.bus_voltage_v",
            "V",
            "interval_mean",
            "Equivalent regulated load-bus voltage associated with the interval power allocation; zero when served load is zero.",
        ),
        (
            "eps.bus_current_a",
            "A",
            "interval_mean",
            "Actually served bus power divided by regulated load-bus voltage.",
        ),
        (
            "eps.battery_temperature_c",
            "degC",
            "endpoint",
            "Lumped battery temperature from converter dissipation, radiation, conduction and sunlight.",
        ),
        (
            "fc.mcu_temperature_c",
            "degC",
            "endpoint",
            "Lumped avionics temperature; does not resolve individual MCU hot spots.",
        ),
        (
            "fc.uptime_s",
            "s",
            "endpoint",
            "Accumulated continuously powered avionics time; reset on loss of supply.",
        ),
        (
            "payload.electronics_temperature_c",
            "degC",
            "endpoint",
            "Lumped payload electronics temperature.",
        ),
        (
            "payload.power_w",
            "W",
            "interval_mean",
            "Payload share of served mode load; included once in the total bus ledger.",
        ),
        (
            "payload.uptime_s",
            "s",
            "endpoint",
            "Continuously fully powered payload duration; reset when inactive or supply is inadequate.",
        ),
        (
            "payload.acquisition_active",
            "1",
            "interval_mean",
            "Model acquisition gate: 1 when the payload is fully powered and scheduled, otherwise 0. Not a mission status code.",
        ),
        (
            "payload.image_count",
            "1",
            "endpoint",
            "Completed modeled image acquisitions; no advancement at the initial sample.",
        ),
        (
            "payload.storage_used_bytes",
            "byte",
            "endpoint",
            "Stored acquisition bytes, bounded by configured capacity; no downlink model.",
        ),
        (
            "payload.storage_fraction",
            "1",
            "endpoint",
            "Stored bytes divided by configured storage capacity.",
        ),
        (
            "adcs.off_nadir_angle_deg",
            "deg",
            "endpoint",
            "Angle between the ideal body +Z axis and Earth center; zero for prescribed nadir pointing.",
        ),
        (
            "adcs.control_error_deg",
            "deg",
            "endpoint",
            "Ideal prescribed pointing error, zero by model assumption; not a solved feedback controller.",
        ),
    ]
    result = [
        ChannelDefinition(name, unit, "scalar", "derived", semantics, None, None, 1, description)
        for name, unit, semantics, description in scalar
    ]
    vectors: list[tuple[str, str, Literal["vector[3]", "vector[4]"], str, str]] = [
        (
            "adcs.attitude_quaternion",
            "1",
            "vector[4]",
            "body_to_GCRS_wxyz",
            "Unit scalar-first quaternion [w,x,y,z], active rotation from LVLH body to GCRS; sign-continuous in time.",
        ),
        (
            "adcs.target_quaternion",
            "1",
            "vector[4]",
            "body_to_GCRS_wxyz",
            "Prescribed ideal nadir target in the same convention as attitude_quaternion.",
        ),
        (
            "adcs.angular_velocity_rad_s",
            "rad/s",
            "vector[3]",
            "body",
            "Body angular velocity relative to GCRS, expressed in body axes, from orbital kinematics.",
        ),
        (
            "adcs.sun_vector_body",
            "1",
            "vector[3]",
            "body",
            "Unit spacecraft-to-Sun direction expressed in LVLH body axes, including during eclipse.",
        ),
        (
            "adcs.magnetic_field_body_t",
            "T",
            "vector[3]",
            "body",
            "Centered aligned Earth dipole approximation in body axes; excludes tilt, multipoles and space weather.",
        ),
        (
            "orbit.position_gcrs_m",
            "m",
            "vector[3]",
            "GCRS",
            "Authoritative backend inertial position, not an averaged source-export position.",
        ),
        (
            "orbit.velocity_gcrs_m_s",
            "m/s",
            "vector[3]",
            "GCRS",
            "Authoritative backend inertial velocity.",
        ),
    ]
    result.extend(
        ChannelDefinition(name, unit, shape, "derived", "endpoint", None, frame, 1, description)
        for name, unit, shape, frame, description in vectors
    )
    unavailable: list[
        tuple[str, str, Literal["scalar", "vector[3]", "vector[4]", "string"], str]
    ] = [
        (
            "eps.watchdog_remaining_s",
            "s",
            "scalar",
            "No ground-command/watchdog reset schedule is modeled.",
        ),
        ("fc.gnss_satellites_in_view", "1", "scalar", "No GNSS constellation or receiver model."),
        ("fc.gnss_satellites_tracked", "1", "scalar", "No GNSS constellation or receiver model."),
        (
            "fc.gnss_fix_quality",
            "unspecified",
            "string",
            "Mission-specific quality codes are undocumented.",
        ),
        (
            "adcs.reaction_wheel_speed_rpm",
            "rpm",
            "vector[4]",
            "No wheel momentum or actuator dynamics model.",
        ),
        (
            "adcs.reaction_wheel_pressure_pa",
            "Pa",
            "vector[4]",
            "No wheel enclosure gas/pressure model.",
        ),
        (
            "adcs.demanded_torque_nm",
            "N*m",
            "vector[3]",
            "Prescribed ideal attitude does not solve actuator torques.",
        ),
        (
            "adcs.controller_mode",
            "unspecified",
            "string",
            "The provided mission mode-code dictionary is unavailable.",
        ),
        (
            "adcs.star_tracker_quality",
            "unspecified",
            "string",
            "No optical tracker/mission quality bitmask model.",
        ),
        (
            "space_weather.kp_index",
            "1",
            "scalar",
            "No geomagnetic activity model or external Kp input.",
        ),
        (
            "space_weather.proton_flux",
            "unspecified",
            "scalar",
            "Source units and external proton-flux model are unspecified.",
        ),
        (
            "space_weather.x_ray_flux",
            "unspecified",
            "scalar",
            "Source units and external solar X-ray model are unspecified.",
        ),
    ]
    result.extend(
        ChannelDefinition(
            name, unit, shape, "derived", "endpoint", None, None, 1, reason, "unavailable"
        )
        for name, unit, shape, reason in unavailable
    )
    return tuple(result)
