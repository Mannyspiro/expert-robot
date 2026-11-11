"""Structural regression checks for the dependency-free mathematics HUD view."""
from pathlib import Path
import unittest

HTML = Path(__file__).resolve().parents[1] / "ui" / "merlin-hud" / "index.html"


class MathematicsHudTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = HTML.read_text(encoding="utf-8")

    def test_mathematics_view_is_navigable(self):
        self.assertIn('data-view="mathematics"', self.source)
        self.assertIn('if(view==="mathematics")', self.source)
        self.assertIn('renderMathLab();', self.source)

    def test_experiment_offers_three_games_and_reproducible_reset(self):
        for token in ('label:"Game A"', 'label:"Game B"', 'label:"Random mix"',
                      'seed:0x51f15e', 'data-math-play="250"'):
            self.assertIn(token, self.source)

    def test_symbolic_explanation_is_gated_until_observation(self):
        self.assertIn('mathState.turn<25', self.source)
        self.assertIn('Reveal the model after 25 turns', self.source)
        self.assertIn('mathState.revealed=true', self.source)

    def test_expected_values_are_explicitly_labelled_as_long_run(self):
        self.assertIn('Long-run stationary expected gain per turn', self.source)
        self.assertIn('not promises about a finite run', self.source)

    def test_math_experiment_has_no_external_dependency(self):
        start = self.source.index('const MATH_GAMES=')
        end = self.source.index('function setWorkspaceView(view)', start)
        experiment = self.source[start:end]
        self.assertNotIn('fetch(', experiment)
        self.assertNotIn('XMLHttpRequest', experiment)
        self.assertNotIn('WebSocket', experiment)


if __name__ == "__main__":
    unittest.main()
