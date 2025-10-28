import os
import shutil
import time
from datetime import datetime

# === Configuration ===
SOURCE_DIR = r"C:\MyFolder"   # Folder you want to back up
BACKUP_DIR = r"C:\backups_of_MyFolder"  # Folder where backups will be stored
BACKUP_INTERVAL_MINUTES = 5              # Backup interval

# === Ensure backup directory exists ===
os.makedirs(BACKUP_DIR, exist_ok=True)

def create_backup():
    """Creates a timestamped copy of SOURCE_DIR inside BACKUP_DIR."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_name = f"1771_backup_{timestamp}"
    dest_path = os.path.join(BACKUP_DIR, backup_name)

    print(f"[{datetime.now()}] Creating backup → {dest_path}")
    try:
        shutil.copytree(SOURCE_DIR, dest_path)
        print(f"[{datetime.now()}] ✅ Backup complete.")
    except Exception as e:
        print(f"[{datetime.now()}] ❌ Error: {e}")

def main():
    print(f"Starting automatic backup every {BACKUP_INTERVAL_MINUTES} minutes...")
    while True:
        create_backup()
        time.sleep(BACKUP_INTERVAL_MINUTES * 60)

if __name__ == "__main__":
    main()
