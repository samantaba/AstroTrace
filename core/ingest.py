import os
import numpy as np
import soundfile as sf

def load_signal(file_path):
data, samplerate = sf.read(file_path)
return data, samplerate

def save_signal(data, samplerate, output_path):
sf.write(output_path, data, samplerate)