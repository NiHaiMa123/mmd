"""No Blender required: test failure contracts and independent job lifecycle."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addon"))
from mmd_outfit import jobs


def temporary_directory():
    root = Path(__file__).resolve().parents[1] / "outputs" / "unit_temp"
    root.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(dir=root)


class RequestTests(unittest.TestCase):
    def test_cuff_physics_is_boolean_and_fit_only(self):
        with temporary_directory() as directory:
            directory=Path(directory);profile=directory/'profile.json';profile.write_text('{}')
            model=directory/'model.pmx';model.write_bytes(b'fixture')
            base={'action':'fit','profile':str(profile),'output_root':str(directory)}
            self.assertTrue(jobs.normalize_request({**base,'cuff_physics':True})['cuff_physics'])
            with self.assertRaisesRegex(ValueError,'boolean'):jobs.normalize_request({**base,'cuff_physics':1})
            with self.assertRaisesRegex(ValueError,'requires fit'):
                jobs.normalize_request({'action':'validate','model':str(model),'output_root':str(directory),'cuff_physics':True})
    def test_grounding_requires_fit_motion_and_boolean_flag(self):
        with temporary_directory() as directory:
            directory=Path(directory);profile=directory/'profile.json';profile.write_text('{}')
            motion=directory/'motion.vmd';motion.write_bytes(b'fixture')
            base={'action':'fit','profile':str(profile),'motion':str(motion),'output_root':str(directory)}
            self.assertTrue(jobs.normalize_request({**base,'ground_motion':True})['ground_motion'])
            with self.assertRaisesRegex(ValueError,'boolean'):jobs.normalize_request({**base,'ground_motion':1})
            missing={**base,'ground_motion':True};missing.pop('motion')
            with self.assertRaisesRegex(ValueError,'requires fit'):jobs.normalize_request(missing)
    def test_missing_input_and_unknown_fields_fail_before_launch(self):
        with self.assertRaisesRegex(ValueError, "Unknown"):
            jobs.normalize_request({"action": "inspect", "soruce": "typo"})
        with self.assertRaisesRegex(ValueError, "Missing"):
            jobs.normalize_request({"action": "inspect", "output_root": "out"})

    def test_nan_timeout_and_boolean_timeout_are_rejected(self):
        with temporary_directory() as directory:
            path = Path(directory) / "profile.json"
            path.write_text("{}")
            for timeout in (True, float("nan"), -1):
                with self.assertRaisesRegex(ValueError, "timeout"):
                    jobs.normalize_request({"action": "fit", "profile": str(path),
                                            "output_root": directory, "timeout": timeout})


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = temporary_directory()
        self.path = Path(self.temp.name)
        self.log = (self.path / "blender.log").open("wb")
        self.process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                                        stdout=self.log, stderr=self.log)
        self.job = jobs.Job(self.process, self.path, self.log, 1800)

    def tearDown(self):
        if self.process.poll() is None:
            self.process.kill()
        self.process.wait()
        self.log.close()
        self.temp.cleanup()

    def test_terminal_status_is_not_a_completed_process_result(self):
        jobs.write_json(self.path / "status.json", {"state": "COMPLETED"})
        self.assertEqual(self.job.poll()["state"], "RUNNING")

    def test_cancel_records_failure_and_stops_only_owned_worker(self):
        result = self.job.cancel()
        self.assertEqual(result["state"], "CANCELLED")
        self.assertFalse(result["ok"])
        self.assertIsNotNone(self.process.poll())

    def test_timeout_is_a_durable_result(self):
        self.job.started = time.monotonic() - 2000
        result = self.job.poll()
        self.assertEqual(result["state"], "TIMED_OUT")
        self.assertEqual(jobs.read_json(self.path / "result.json")["state"], "TIMED_OUT")

    def test_crash_without_result_cannot_pass(self):
        self.process.kill()
        self.process.wait()
        result = self.job.poll()
        self.assertEqual(result["state"], "FAILED")
        self.assertIn("without a result", result["error"]["message"])


if __name__ == "__main__":
    unittest.main()
