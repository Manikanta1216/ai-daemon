import os
import shutil
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("reset_faces")

def reset_all_face_data():
    """
    Cleans the structure and removes all cached/registered face data.
    """
    logger.info("Starting fresh: Cleaning all face registration data...")

    # 1. Define paths
    base_dir = Path(__file__).parent
    samples_dir = base_dir / "samples"
    trainer_dir = base_dir / "Face Recognition" / "trainer"
    trainer_file = trainer_dir / "trainer.yml"
    users_file = base_dir / "users.json"
    intruders_dir = base_dir / "intruders"
    registered_dir = base_dir / "registered_faces"
    memory_dir = base_dir / "memory"

    # 1.5 Clear memory
    if memory_dir.exists():
        logger.info(f"Clearing memory files in {memory_dir}...")
        for file in memory_dir.glob("*.json"):
            file.unlink()
    else:
        memory_dir.mkdir(parents=True, exist_ok=True)

    # 2. Clear samples
    if samples_dir.exists():
        logger.info(f"Clearing samples in {samples_dir}...")
        for file in samples_dir.glob("*.jpg"):
            file.unlink()
    else:
        samples_dir.mkdir(parents=True, exist_ok=True)

    # 3. Delete trainer file
    if trainer_file.exists():
        logger.info(f"Deleting trainer model: {trainer_file}")
        trainer_file.unlink()
    
    if not trainer_dir.exists():
        trainer_dir.mkdir(parents=True, exist_ok=True)

    # 4. Reset users.json
    if users_file.exists():
        logger.info(f"Resetting {users_file}...")
        users_file.unlink()
    
    with open(users_file, "w") as f:
        f.write("{}")

    # 5. Clear intruders
    if intruders_dir.exists():
        logger.info(f"Clearing intruder logs in {intruders_dir}...")
        for file in intruders_dir.glob("*.jpg"):
            file.unlink()
    else:
        intruders_dir.mkdir(parents=True, exist_ok=True)

    # 6. Clear registered faces (if any)
    if registered_dir.exists():
        logger.info(f"Clearing registered faces in {registered_dir}...")
        for file in registered_dir.glob("*"):
            if file.is_file():
                file.unlink()
            elif file.is_dir():
                shutil.rmtree(file)
    else:
        registered_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Structure cleaned perfectly. You can now start fresh.")

if __name__ == "__main__":
    reset_all_face_data()
