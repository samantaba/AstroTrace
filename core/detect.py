import numpy as np

def detect_anomalies(signal_data, threshold=2.5):
std = np.std(signal_data)
mean = np.mean(signal_data)
anomalies = np.where(np.abs(signal_data - mean) > threshold * std)[0]
return anomalies