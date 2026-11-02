"""Radius-independent garment displacement; NumPy ships with Blender."""
import numpy as np


class RadialEnvelopeField:
    """Radius-independent outward offsets preserve the order of garment layers.

    A periodic angular/height field is shared by all layers on a radial ray.
    Unlike a nearest-surface projection it cannot collapse those layers onto
    the same radius. Gaussian maxima spread required space to nearby fabric.
    """
    def __init__(self, angles, heights, amounts, angular_radius=0.22, height_radius=0.025):
        points = np.column_stack((angles, heights))
        amounts = np.asarray(amounts, dtype=float)
        if not len(points) or amounts.shape != (len(points),) or not np.isfinite(points).all() or not np.isfinite(amounts).all() or (amounts < 0).any():
            raise ValueError("Expected nonempty finite angular/height controls and nonnegative offsets")
        if not angular_radius > 0 or not height_radius > 0:
            raise ValueError("Field radii must be positive")
        bins = np.floor(points / (0.04, 0.006)).astype(np.int64)
        _, groups = np.unique(bins, axis=0, return_inverse=True)
        self.centers = np.zeros((groups.max() + 1, 2))
        np.add.at(self.centers, groups, points)
        self.centers /= np.bincount(groups)[:, None]
        self.amounts = np.zeros(len(self.centers))
        delta = points - self.centers[groups]
        angle = (delta[:, 0] + np.pi) % (2*np.pi) - np.pi
        kernel = np.exp(-.5*((angle/angular_radius)**2 + (delta[:, 1]/height_radius)**2))
        # Binning moves a control away from its own center. Compensate that
        # attenuation so the envelope still meets every original requirement.
        np.maximum.at(self.amounts, groups, amounts/kernel)
        active = self.amounts > 0
        self.centers, self.amounts = self.centers[active], self.amounts[active]
        self.angular_radius = angular_radius
        self.height_radius = height_radius

    def evaluate(self, angles, heights):
        points = np.column_stack((angles, heights))
        if not len(self.centers):
            return np.zeros(len(points))
        result = np.empty(len(points))
        for start in range(0, len(points), 1024):
            delta = points[start:start + 1024, None, :] - self.centers[None, :, :]
            angle = (delta[:, :, 0] + np.pi) % (2 * np.pi) - np.pi
            distance = (angle / self.angular_radius) ** 2 + (delta[:, :, 1] / self.height_radius) ** 2
            result[start:start + 1024] = np.max(self.amounts * np.exp(-distance / 2), axis=1)
        return result


