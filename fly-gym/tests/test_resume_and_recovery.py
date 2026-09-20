import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from checkpoint_selection import resolve_resume_checkpoint
from agents.teacher_analytic_agent import PlannerAnalyticTeacher


class ResumeTests(unittest.TestCase):
    def test_latest_uses_save_time_and_includes_final_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            final = root / "connectome_rnn_dagger_princeton.pt"
            self.assertIsNone(resolve_resume_checkpoint("latest", root, final))
            for name, stamp in [
                ("connectome_rnn_dagger_iter_9.pt", 100),
                ("connectome_rnn_dagger_iter_1.pt", 200),
                ("vision_iter_10.pt", 400),
            ]:
                path = root / name
                path.touch()
                os.utime(path, (stamp, stamp))
            selected = resolve_resume_checkpoint("latest", root, final)
            self.assertEqual(Path(selected).name, "connectome_rnn_dagger_iter_1.pt")
            final.touch()
            os.utime(final, (300, 300))
            self.assertEqual(resolve_resume_checkpoint("latest", root, final), str(final))
            self.assertIsNone(resolve_resume_checkpoint(None, root, final))
            self.assertEqual(resolve_resume_checkpoint(selected, root, final), selected)
            with self.assertRaises(FileNotFoundError):
                resolve_resume_checkpoint(root / "missing.pt", root, final)


class RecoveryTests(unittest.TestCase):
    def test_back_then_turn_with_consistent_direction_and_replan(self):
        for direction in (-1.0, 1.0):
            teacher = PlannerAnalyticTeacher(arena_half_extent=7)
            teacher._rec_phase = "back"
            teacher._rec_turn_dir = direction
            for step in range(teacher.recovery_back_steps + teacher.recovery_turn_steps):
                action, replan = teacher._step_recovery()
                if step < teacher.recovery_back_steps:
                    self.assertLess(action[0], 0)
                else:
                    self.assertEqual(action[0], 0)
                    self.assertAlmostEqual(float(action[1]), 1.2 * direction, places=6)
                self.assertEqual(replan, step == 44)
            self.assertIsNone(teacher._rec_phase)
            self.assertEqual(teacher._rec_step_count, 0)


if __name__ == "__main__":
    unittest.main()
