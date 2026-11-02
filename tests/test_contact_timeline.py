"""A 60 Hz motion reference must not be indexed as a 30 Hz solver cache."""
import sys
import unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'addon'))
from mmd_outfit.contact_timeline import reference_times,reference_at_time


class ContactTimelineTests(unittest.TestCase):
    def test_subframe_reference_at_output_times(self):
        times=reference_times({'fps':30,'sample_times_s':[0,1/60,1/30,.04,2/30]},5)
        positions=np.array([0,100,2,80,4.])[:,None,None]
        np.testing.assert_allclose([reference_at_time(positions,times,k/30).item() for k in range(3)],[0,2,4])

    def test_interpolates_nonuniform_keys(self):
        times=reference_times({'fps':30,'sample_times_s':[0,.1,.3]},3)
        self.assertAlmostEqual(reference_at_time(np.array([0.,1.,5.]),times,.2),3)

    def test_legacy_uniform_and_bounds(self):
        times=reference_times({'fps':30},3)
        np.testing.assert_allclose(times,[0,1/30,2/30])
        with self.assertRaises(ValueError):reference_at_time(np.zeros(3),times,.2)
        with self.assertRaises(ValueError):reference_times({'fps':30,'sample_times_s':[0,0]},2)
        with self.assertRaises(ValueError):reference_times({'fps':0},3)


if __name__=='__main__':unittest.main()
