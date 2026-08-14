import unittest

from intelligent_gait_interpretation import MetricAnalyzer, ReferenceDatabase


class TestIntelligentGaitInterpretation(unittest.TestCase):
    def test_analyze_returns_scores_and_interpretation(self):
        samples = []
        for i in range(20):
            angle = 10 + 4 * (i % 4) + 0.3 * ((-1) ** i)
            samples.append((i * 0.1, angle, 0.0, 0.0))

        db = ReferenceDatabase.from_defaults()
        analyzer = MetricAnalyzer(db)
        result = analyzer.analyze(samples)

        self.assertIn("overall_quality_score", result)
        self.assertIn("movement_symmetry_score", result)
        self.assertIn("interpretation", result)
        self.assertGreaterEqual(result["overall_quality_score"], 0)
        self.assertLessEqual(result["overall_quality_score"], 100)
        self.assertGreaterEqual(result["confidence_score"], 0)
        self.assertLessEqual(result["confidence_score"], 100)


if __name__ == "__main__":
    unittest.main()
