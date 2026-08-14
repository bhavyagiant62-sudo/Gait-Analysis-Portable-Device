from __future__ import annotations

import statistics
from typing import List, Tuple


class KinematicsAnalyzer:
    """
    Calculates kinematic measures directly derivable from a single-axis
    knee angle (pitch) time series: no distance/pressure sensor required.

    Input samples are (time_ms, pitch_deg) pairs, oldest first.
    """

    def __init__(self):
        self.metrics = {}

    def update(self, samples: List[Tuple[float, float]]) -> dict:
        if len(samples) < 2:
            return self._empty_metrics()

        recent = samples[-500:]
        times = [s[0] / 1000.0 for s in recent]     # seconds
        angles = [s[1] for s in recent]

        max_val = max(angles)
        min_val = min(angles)
        avg_val = statistics.mean(angles)
        rom = max_val - min_val

        # Angular velocity omega(t) = d(theta)/dt, deg/s, sample-to-sample
        velocities = [
            (angles[i] - angles[i - 1]) / max(times[i] - times[i - 1], 1e-6)
            for i in range(1, len(angles))
        ]
        peak_velocity = max((abs(v) for v in velocities), default=0.0)
        mean_abs_velocity = statistics.mean(abs(v) for v in velocities) if velocities else 0.0

        # Angular acceleration alpha(t) = d(omega)/dt, deg/s^2
        accelerations = [
            (velocities[i] - velocities[i - 1]) / max(times[i + 1] - times[i], 1e-6)
            for i in range(1, len(velocities))
        ]
        peak_acceleration = max((abs(a) for a in accelerations), default=0.0)
        mean_abs_acceleration = statistics.mean(abs(a) for a in accelerations) if accelerations else 0.0

        # Jerk = d(alpha)/dt, deg/s^3 - a common smoothness proxy in gait research
        jerks = [
            (accelerations[i] - accelerations[i - 1]) / max(times[i + 2] - times[i + 1], 1e-6)
            for i in range(1, len(accelerations))
        ]
        mean_abs_jerk = statistics.mean(abs(j) for j in jerks) if jerks else 0.0

        # Signal RMS = sqrt(mean(theta^2))
        signal_rms = (sum(a ** 2 for a in angles) / len(angles)) ** 0.5

        # Coefficient of variation = stdev / mean (dispersion relative to signal level)
        coefficient_of_variation = (
            statistics.pstdev(angles) / abs(avg_val) if avg_val != 0 else 0.0
        )
        motion_variability = coefficient_of_variation

        joint_stability = max(0.0, 1.0 - motion_variability)
        # Movement smoothness: 1.0 = perfectly smooth, decays as jerk grows
        movement_smoothness = max(0.0, 1.0 - min(mean_abs_jerk / 2000.0, 1.0))

        self.metrics = {
            "knee_flexion": max_val,
            "knee_extension": min_val,
            "max_flexion": max_val,
            "max_extension": min_val,
            "rom": rom,
            "average_knee_angle": avg_val,
            "angular_velocity": mean_abs_velocity,
            "peak_angular_velocity": peak_velocity,
            "angular_acceleration": mean_abs_acceleration,
            "peak_angular_acceleration": peak_acceleration,
            "jerk": mean_abs_jerk,
            "signal_rms": signal_rms,
            "coefficient_of_variation": coefficient_of_variation,
            "motion_variability": motion_variability,
            "joint_stability": joint_stability,
            "joint_smoothness_index": movement_smoothness,
            "movement_smoothness": movement_smoothness,
            "status": "Calculated from successive angle samples and their real time deltas",
        }
        return self.metrics

    def _empty_metrics(self) -> dict:
        self.metrics = {
            "knee_flexion": 0.0,
            "knee_extension": 0.0,
            "max_flexion": 0.0,
            "max_extension": 0.0,
            "rom": 0.0,
            "average_knee_angle": 0.0,
            "angular_velocity": 0.0,
            "peak_angular_velocity": 0.0,
            "angular_acceleration": 0.0,
            "peak_angular_acceleration": 0.0,
            "jerk": 0.0,
            "signal_rms": 0.0,
            "coefficient_of_variation": 0.0,
            "motion_variability": 0.0,
            "joint_stability": 0.0,
            "joint_smoothness_index": 0.0,
            "movement_smoothness": 0.0,
            "status": "Waiting for angle data",
        }
        return self.metrics
