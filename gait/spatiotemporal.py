from __future__ import annotations


class SpatiotemporalAnalyzer:
    """
    Splits spatiotemporal gait parameters into two honest categories:

    1. Timing parameters computable from a single knee-angle IMU stream
       via gait-cycle (peak) detection - cadence, step count, walking/
       stride frequency, gait cycle time, cycle time variability.
    2. Spatial parameters that fundamentally require a distance or
       position reference (stereo camera, floor sensor, GPS/UWB, a second
       calibrated IMU with stride-length integration, etc.) that this
       single-IMU wearable does not have. These are reported honestly as
       unavailable rather than guessed.
    """

    def __init__(self):
        self.metrics = {}

    def update(self, gait_metrics: dict) -> dict:
        cadence = gait_metrics.get("cadence", 0.0)
        step_count = gait_metrics.get("step_count", 0)
        walking_frequency = gait_metrics.get("walking_frequency", 0.0)
        gait_cycle_duration = gait_metrics.get("gait_cycle_duration", 0.0)
        cycle_time_cv = gait_metrics.get("cycle_time_variability", 0.0)
        duration_s = gait_metrics.get("observation_duration_s", 0.0)

        step_time = 60.0 / cadence if cadence > 0 else 0.0
        stride_time = gait_cycle_duration if gait_cycle_duration else (2.0 * step_time)
        stride_frequency = walking_frequency / 2.0 if walking_frequency else 0.0

        unavailable = "Requires an additional distance/position reference (e.g. stereo camera, floor pressure mat, UWB/GPS, or calibrated stride-length integration) not present on this single-IMU wearable."

        self.metrics = {
            # --- computable from this sensor's timing ---
            "cadence": cadence,
            "step_count": step_count,
            "walking_frequency": walking_frequency,
            "stride_frequency": stride_frequency,
            "step_time": step_time,
            "stride_time": stride_time,
            "gait_cycle_time": gait_cycle_duration,
            "cycle_time_variability": cycle_time_cv,
            "observation_duration_s": duration_s,
            # --- genuinely unavailable on this hardware ---
            "walking_velocity": unavailable,
            "step_length": unavailable,
            "stride_length": unavailable,
            "step_width": unavailable,
            "foot_progression_angle": unavailable,
            "foot_angle": unavailable,
            "single_support_time": unavailable,
            "double_support_time": unavailable,
            "stance_time": unavailable,
            "swing_time": unavailable,
            "walking_symmetry_index": "Requires a second, time-synchronized IMU on the contralateral limb to compare left/right timing directly.",
            "walking_efficiency_score": unavailable,
        }
        return self.metrics
