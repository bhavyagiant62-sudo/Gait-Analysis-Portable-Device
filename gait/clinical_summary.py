from __future__ import annotations


class ClinicalSummaryGenerator:
    """Generates descriptive (non-diagnostic) clinical notes from computed gait metrics."""

    def __init__(self):
        self.summary = {}

    def update(self, rom: float, cadence: float, joint_stability: float = 1.0,
               movement_smoothness: float = 1.0, cycle_time_variability: float = 0.0) -> dict:
        if rom < 20:
            stiffness = "Reduced flexion-extension excursion"
        elif rom > 70:
            stiffness = "Increased range of motion"
        else:
            stiffness = "Moderate excursion"

        if cadence <= 0:
            pattern = "No walking activity detected in the current window"
        elif cadence < 80:
            pattern = "Slow walking pattern"
        elif cadence > 120:
            pattern = "Fast walking pattern"
        else:
            pattern = "Normal walking cadence range"

        if joint_stability >= 0.8:
            stability_note = "Stable joint trajectory across observed cycles"
        elif joint_stability >= 0.6:
            stability_note = "Mild instability observed during the gait cycle"
        else:
            stability_note = "Notable instability / inconsistency in joint trajectory"

        if movement_smoothness >= 0.8:
            smoothness_note = "Smooth angular motion (low jerk)"
        elif movement_smoothness >= 0.6:
            smoothness_note = "Some jerkiness in the movement trajectory"
        else:
            smoothness_note = "High jerk suggests reduced movement smoothness"

        if cycle_time_variability <= 0.1:
            rhythm_note = "Consistent step-to-step timing"
        elif cycle_time_variability <= 0.2:
            rhythm_note = "Mild step-to-step timing variability"
        else:
            rhythm_note = "High step-to-step timing variability"

        self.summary = {
            "clinical_summary": "Movement characteristics based on observed knee angle signal, cadence, stability, and smoothness.",
            "walking_pattern": pattern,
            "joint_stiffness": stiffness,
            "stability_note": stability_note,
            "smoothness_note": smoothness_note,
            "rhythm_note": rhythm_note,
            "reduced_flexion": rom < 30,
            "reduced_extension": rom < 10,
            "asymmetry": "Requires bilateral (left + right) or repeated-trial data for stronger interpretation.",
            "possible_gait_abnormality": "Descriptive movement characteristic only; not a diagnosis.",
        }
        return self.summary
