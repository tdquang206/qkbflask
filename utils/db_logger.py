import os, json, datetime, shutil, glob

LOG_DIR = "logs"
BACKUP_DIR = "backups"

os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)

def log_action(action, payload, db_name="db.json"):
    now = datetime.datetime.now()
    month_file = os.path.join(LOG_DIR, f"db_{now.strftime('%Y_%m')}.log")
    entry = {
        "action": action,
        "timestamp": now.isoformat(),
        "payload": payload
    }
    with open(month_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def weekly_backup_all():
    """Backup all db*.json files once per week."""
    now = datetime.datetime.now()
    week_id = now.strftime("%Y_%W")
    os.makedirs(BACKUP_DIR, exist_ok=True)

    for db_path in glob.glob("db*.json"):
        base = os.path.basename(db_path).replace(".json", "")
        backup_file = os.path.join(BACKUP_DIR, f"{base}_backup_{week_id}.json")
        if not os.path.exists(backup_file):
            shutil.copy(db_path, backup_file)
            print(f"Backup created: {backup_file}")

def rotate_backups(max_files=100):
    for db_file in glob.glob(os.path.join(BACKUP_DIR, "*_backup_*.json")):
        base = "_".join(os.path.basename(db_file).split("_backup_")[0].split("_")[:-1])
        matching = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith(base)], reverse=True)
        for old in matching[max_files:]:
            os.remove(os.path.join(BACKUP_DIR, old))
