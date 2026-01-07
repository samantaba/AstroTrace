import os
import time
import threading
from core.transcriber import Transcriber
from core.logger import EventLogger

class FileWatcher(threading.Thread):
def __init__(self, watch_dir, interval=5):
super().__init__()
self.watch_dir = watch_dir
self.interval = interval
self.running = True
self.seen_files = set()
self.transcriber = Transcriber()
self.logger = EventLogger()

def run(self):
while self.running:
for fname in os.listdir(self.watch_dir):
if fname.endswith(".wav") and fname not in self.seen_files:
filepath = os.path.join(self.watch_dir, fname)
print(f"[Watcher] Processing new file: {filepath}")
text = self.transcriber.transcribe_file(filepath)
self.logger.log_event(freq=0.0, text=text, source='watcher')
self.seen_files.add(fname)
time.sleep(self.interval)

def stop(self):
self.running = False