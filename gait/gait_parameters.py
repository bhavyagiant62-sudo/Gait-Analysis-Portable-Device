from __future__ import annotations

import statistics
from typing import List, Tuple


class GaitParameterCalculator:
    """
    Calculates gait-cycle-based parameters (cadence, step count, walking
    frequency, gait cycle duration) from the knee flexion/extension (pitch)
    signal by detecting flexion peaks - i.e. actual gait cycles - rather
    than guessing from packet count.

    Input samples are (time_ms, pitch_deg) pairs, oldest first. `time_ms`
    is the ESP32's onboard millis() timestamp carried in each UDP packet.
    """

    MIN_PEAK_PROMINENCE_DEG = 5.0   # ignore tiny wobble as a "step"
    MIN_PEAK_DISTANCE_S = 0.4       # fastest plausible step cadence (~150 spm)

    def __init__(self):
        self._samples: List[Tuple[float, float]] = []

    def update(self, samples: List[Tuple[float, float]]) -> dict:
        """samples: list of (time_ms, pitch_deg), most recent last."""
        self._samples = samples[-2000:]
        if len(self._samples) < 3:
            return self._empty_metrics()

        times = [s[0] / 1000.0 for s in self._samples]   # -> seconds
        angles = [s[1] for s in self._samples]

        maximum = max(angles)
        minimum = min(angles)
        average = statistics.mean(angles)
        rom = maximum - minimum

        peak_indices = self._detect_peaks(times, angles)
        duration_s = max(times[-1] - times[0], 1e-6)
        duration_min = duration_s / 60.0

        step_count = len(peak_indices)
        # Cadence here is single-limb: steps detected on THIS sensor only.
        # Formula: cadence (steps/min) = detected_peaks / elapsed_minutes
        cadence = step_count / duration_min if duration_min > 0 else 0.0

        if len(peak_indices) >= 2:
            peak_intervals = [
                times[peak_indices[i]] - times[peak_indices[i - 1]]
                for i in range(1, len(peak_indices))
            ]
            gait_cycle_duration = statistics.mean(peak_intervals)
            cycle_time_cv = (
                statistics.pstdev(peak_intervals) / statistics.mean(peak_intervals)
                if statistics.mean(peak_intervals) > 0 else 0.0
            )
        else:
            gait_cycle_duration = 0.0
            cycle_time_cv = 0.0

        # Walking (step) frequency in Hz = cadence / 60
        walking_frequency = cadence / 60.0

        return {
            "max_flexion": maximum,
            "max_extension": minimum,
            "rom": rom,
            "average_angle": average,
            "step_count": step_count,
            "cadence": cadence,
            "walking_frequency": walking_frequency,
            "gait_cycle_duration": gait_cycle_duration,
            "cycle_time_variability": cycle_time_cv,
            "observation_duration_s": duration_s,
            "peak_indices": peak_indices,
            "status": "Calculated from detected flexion peaks in the pitch signal",
        }

    def _detect_peaks(self, times: List[float], angles: List[float]) -> List[int]:
        """
        Simple local-maximum peak detector with a minimum time gap and a
        minimum prominence (rise above the preceding local minimum), used
        as a stand-in for true gait-event (heel-strike) detection since
        this system has no foot-switch/pressure reference.
        """
        peaks: List[int] = []
        last_trough = angles[0]
        i = 1
        while i < len(angles) - 1:
            is_local_max = angles[i] >= angles[i - 1] and angles[i] >= angles[i + 1]
            if is_local_max:
                prominence = angles[i] - last_trough
                far_enough = (
                    not peaks or (times[i] - times[peaks[-1]]) >= self.MIN_PEAK_DISTANCE_S
                )
                if prominence >= self.MIN_PEAK_PROMINENCE_DEG and far_enough:
                    peaks.append(i)
                    last_trough = angles[i]
            else:
                last_trough = min(last_trough, angles[i])
            i += 1
        return peaks

    def _empty_metrics(self) -> dict:
        return {
            "max_flexion": 0.0,
            "max_extension": 0.0,
            "rom": 0.0,
            "average_angle": 0.0,
            "step_count": 0,
            "cadence": 0.0,
            "walking_frequency": 0.0,
            "gait_cycle_duration": 0.0,
            "cycle_time_variability": 0.0,
            "observation_duration_s": 0.0,
            "peak_indices": [],
            "status": "Waiting for gait data",
        }
