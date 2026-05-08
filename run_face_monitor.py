# run_face_monitor.py
import os, sys
sys.path.append(os.path.abspath("c:/Users/ADMIN/folder"))

from modules.face_monitor_module import start_face_monitor, stop_face_monitor

print(start_face_monitor())
input("Press ENTER to stop the monitor…")
print(stop_face_monitor())
