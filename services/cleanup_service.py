import os
import time
from config import Config

def cleanup_old_files(folder, max_age_seconds=86400):
    deleted = 0
    if not os.path.isdir(folder):
        return deleted
    now = time.time()
    for filename in os.listdir(folder):
        filepath = os.path.join(folder, filename)
        if os.path.isfile(filepath):
            try:
                if now - os.path.getmtime(filepath) > max_age_seconds:
                    os.remove(filepath)
                    deleted += 1
            except Exception:
                pass
    return deleted

def run_cleanup():
    from models import get_db
    uploads_deleted = cleanup_old_files(Config.UPLOAD_FOLDER)
    exports_deleted = cleanup_old_files('exports')
    total = uploads_deleted + exports_deleted
    try:
        db = get_db()
        db.execute(
            'INSERT INTO system_logs (level, source, message, details) VALUES (?, ?, ?, ?)',
            (
                'INFO',
                'cleanup',
                f'Auto-cleanup removed {total} file(s) older than 24 hours',
                f'uploads: {uploads_deleted} file(s) deleted, exports: {exports_deleted} file(s) deleted',
            ),
        )
        db.commit()
        db.close()
    except Exception:
        pass
