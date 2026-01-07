def compute_power(samples):
"""Compute average signal power from complex samples."""
import numpy as np
return np.mean(np.abs(samples) ** 2)


def frequency_to_mhz(freq):
"""Convert Hz to MHz with 3 decimal places."""
return round(freq / 1e6, 3)


def timestamp_now():
from datetime import datetime
return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")