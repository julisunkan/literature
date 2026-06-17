import os
import time
import logging
from flask import Flask, render_template, jsonify
from config import Config
from models import init_db

logging.getLogger('apscheduler').setLevel(logging.WARNING)

def _cleanup_old_files(folder, max_age_seconds=86400):
    if not os.path.isdir(folder):
        return
    now = time.time()
    for filename in os.listdir(folder):
        filepath = os.path.join(folder, filename)
        if os.path.isfile(filepath):
            try:
                if now - os.path.getmtime(filepath) > max_age_seconds:
                    os.remove(filepath)
            except Exception:
                pass

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config['SECRET_KEY'] = Config.SECRET_KEY
    app.config['MAX_CONTENT_LENGTH'] = Config.MAX_CONTENT_LENGTH

    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
    os.makedirs('exports', exist_ok=True)
    os.makedirs('backups', exist_ok=True)

    with app.app_context():
        init_db()

    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(
        func=lambda: [
            _cleanup_old_files(Config.UPLOAD_FOLDER),
            _cleanup_old_files('exports'),
        ],
        trigger='interval',
        hours=1,
        id='file_cleanup',
        replace_existing=True,
    )
    scheduler.start()

    from blueprints.main import main_bp
    from blueprints.ai_features import ai_bp
    from blueprints.export_bp import export_bp
    from blueprints.admin import admin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(admin_bp)

    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        from models import get_db
        try:
            db = get_db()
            db.execute('INSERT INTO system_logs (level, source, message) VALUES (?, ?, ?)',
                       ('ERROR', 'app', str(e)[:500]))
            db.commit()
            db.close()
        except Exception:
            pass
        return render_template('errors/500.html'), 500

    @app.context_processor
    def inject_globals():
        from models import get_db
        try:
            db = get_db()
            site = {r['key']: r['value'] for r in db.execute('SELECT key, value FROM site_settings').fetchall()}
            pwa = {r['key']: r['value'] for r in db.execute('SELECT key, value FROM pwa_settings').fetchall()}
            notif_count = db.execute('SELECT COUNT(*) as c FROM notifications WHERE is_read=0').fetchone()['c']
            db.close()
        except Exception:
            site = {'site_name': 'Literature Review Generator'}
            pwa = {'theme_color': '#2563eb'}
            notif_count = 0
        return {'g_site': site, 'g_pwa': pwa, 'g_notif_count': notif_count}

    return app

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
