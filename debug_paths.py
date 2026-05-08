import os
from config import PROJECT_ROOT

print(f"PROJECT_ROOT: {PROJECT_ROOT}")
faces_dir = os.path.join(PROJECT_ROOT, "registered_faces")
print(f"faces_dir: {faces_dir}")
if os.path.exists(faces_dir):
    files = os.listdir(faces_dir)
    print(f"Number of files: {len(files)}")
    print(f"Files: {files}")
else:
    print("Directory does not exist")
