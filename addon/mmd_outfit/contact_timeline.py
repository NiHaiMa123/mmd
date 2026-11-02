"""Sample contact references at solver times, including subframe motion keys."""
import numpy as np


def reference_times(manifest, count):
    fps = float(manifest['fps'])
    if not np.isfinite(fps) or fps <= 0:
        raise ValueError('Reference fps must be positive')
    times = np.asarray(manifest.get('sample_times_s', np.arange(count) / fps), dtype=float)
    if (times.shape != (count,) or not np.isfinite(times).all()
            or count < 1 or (np.diff(times) <= 0).any()):
        raise ValueError('Reference times must match samples and increase strictly')
    return times


def reference_at_time(values, times, time):
    """Linear interpolation matching PPF's prescribed animation tracks.

    Reject extrapolation: a short or incomplete cache is not evidence about
    motion outside its actual reference range.
    """
    if not np.isfinite(time) or time < times[0] - 1e-8 or time > times[-1] + 1e-8:
        raise ValueError('Solver sample is outside the reference timeline')
    time = float(np.clip(time, times[0], times[-1]))
    right = int(np.searchsorted(times, time, side='left'))
    if right == 0:
        return values[0]
    if right == len(times):
        return values[-1]
    left = right - 1
    weight = (time - times[left]) / (times[right] - times[left])
    return values[left] * (1 - weight) + values[right] * weight
