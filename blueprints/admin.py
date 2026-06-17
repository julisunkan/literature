from flask import Blueprint, render_template, request, jsonify, redirect, url_for, send_file
from models import get_db
import json, os, shutil
from datetime import datetime

admin_bp = Blueprint('admin', __name__, url_prefix='/julisunkan')

def get_site_settings():
    db = get_db()
    rows = db.execute('SELECT key, value FROM site_settings').fetchall()
    db.close()
    return {r['key']: r['value'] for r in rows}

def log_audit(action, entity_type='', entity_id='', old_val='', new_val=''):
    try:
        db = get_db()
        ip = request.remote_addr or ''
        db.execute('INSERT INTO audit_logs (admin_action, entity_type, entity_id, old_value, new_value, ip_address) VALUES (?,?,?,?,?,?)',
                   (action, entity_type, str(entity_id), str(old_val)[:500], str(new_val)[:500], ip))
        db.commit()
        db.close()
    except Exception:
        pass

@admin_bp.route('/')
def dashboard():
    from config import Config
    site = get_site_settings()
    db = get_db()
    stats = {
        'papers': db.execute('SELECT COUNT(*) as c FROM papers').fetchone()['c'],
        'reviews': db.execute('SELECT COUNT(*) as c FROM literature_reviews').fetchone()['c'],
        'uploads': db.execute('SELECT COUNT(*) as c FROM uploads').fetchone()['c'],
        'ai_requests': db.execute("SELECT COUNT(*) as c FROM system_logs WHERE source LIKE 'ai:%'").fetchone()['c'],
        'errors': db.execute("SELECT COUNT(*) as c FROM system_logs WHERE level='ERROR'").fetchone()['c'],
        'chat_sessions': db.execute('SELECT COUNT(*) as c FROM chat_sessions').fetchone()['c'],
        'exports': db.execute('SELECT COUNT(*) as c FROM exports').fetchone()['c'],
    }
    recent_logs = db.execute('SELECT * FROM system_logs ORDER BY created_at DESC LIMIT 10').fetchall()
    recent_activity = db.execute('SELECT * FROM activity_logs ORDER BY created_at DESC LIMIT 10').fetchall()

    api_rows = db.execute('SELECT name, key_value FROM api_settings').fetchall()
    db.close()
    db_keys = {r['name']: r['key_value'] for r in api_rows}

    def _has_key(db_name, env_val):
        return bool((db_keys.get(db_name) or '').strip() or (env_val or '').strip())

    ollama_url = (db_keys.get('ollama_url') or Config.OLLAMA_URL or '').strip()
    ollama_ok = bool(ollama_url) and 'localhost' not in ollama_url and '127.0.0.1' not in ollama_url

    ai_provider_status = [
        {'name': 'Groq',        'ok': _has_key('groq_api_key',        Config.GROQ_API_KEY),       'url': '/julisunkan/api-management'},
        {'name': 'OpenRouter',  'ok': _has_key('openrouter_api_key',  Config.OPENROUTER_API_KEY),  'url': '/julisunkan/api-management'},
        {'name': 'Gemini',      'ok': _has_key('gemini_api_key',      Config.GEMINI_API_KEY),      'url': '/julisunkan/api-management'},
        {'name': 'Ollama',      'ok': ollama_ok,                                                    'url': '/julisunkan/api-management'},
    ]
    any_ai_configured = any(p['ok'] for p in ai_provider_status)

    return render_template('admin/dashboard.html', site=site, stats=stats,
                           recent_logs=recent_logs, recent_activity=recent_activity,
                           ai_provider_status=ai_provider_status,
                           any_ai_configured=any_ai_configured)

@admin_bp.route('/settings', methods=['GET', 'POST'])
def settings():
    site = get_site_settings()
    if request.method == 'POST':
        data = request.form
        db = get_db()
        for key in ['site_name', 'site_tagline', 'footer_text', 'contact_email',
                    'about_text', 'privacy_policy', 'terms']:
            if key in data:
                old = site.get(key, '')
                db.execute('INSERT OR REPLACE INTO site_settings (key, value) VALUES (?, ?)',
                           (key, data[key]))
                log_audit('settings_update', 'site_settings', key, old, data[key])
        db.commit()
        db.close()
        return redirect(url_for('admin.settings'))
    return render_template('admin/settings.html', site=site)

@admin_bp.route('/api-management', methods=['GET', 'POST'])
def api_management():
    site = get_site_settings()
    db = get_db()
    apis = db.execute('SELECT * FROM api_settings ORDER BY name').fetchall()
    models = db.execute('SELECT * FROM ai_models ORDER BY provider, is_default DESC').fetchall()
    db.close()
    return render_template('admin/api_management.html', site=site, apis=apis, models=models)

@admin_bp.route('/api/api-settings', methods=['POST'])
def update_api_setting():
    data = request.get_json()
    name = data.get('name')
    value = data.get('value', '')
    enabled = data.get('enabled', 1)
    db = get_db()
    old = db.execute('SELECT key_value FROM api_settings WHERE name=?', (name,)).fetchone()
    db.execute('INSERT OR REPLACE INTO api_settings (name, key_value, is_enabled, provider_type) VALUES (?, ?, ?, ?)',
               (name, value, enabled, data.get('provider_type', 'ai')))
    db.commit()
    db.close()
    log_audit('api_key_update', 'api_settings', name, '***', '***')
    return jsonify({'success': True})

@admin_bp.route('/api/test-api', methods=['POST'])
def test_api():
    data = request.get_json()
    name = data.get('name', '')
    db = get_db()
    api = db.execute('SELECT * FROM api_settings WHERE name=?', (name,)).fetchone()
    db.close()
    if not api:
        return jsonify({'success': False, 'error': 'API not found'})
    try:
        if 'groq' in name:
            import requests as req
            headers = {'Authorization': f'Bearer {api["key_value"]}', 'Content-Type': 'application/json'}
            r = req.get('https://api.groq.com/openai/v1/models', headers=headers, timeout=10)
            success = r.status_code == 200
            msg = 'Connected successfully' if success else f'Error: {r.status_code}'
        elif 'ollama' in name:
            import requests as req
            r = req.get(f'{api["key_value"]}/api/tags', timeout=5)
            success = r.status_code == 200
            msg = 'Ollama running' if success else 'Cannot connect'
        else:
            success = bool(api['key_value'])
            msg = 'Key present' if success else 'No key configured'
        status = 'ok' if success else 'error'
        db = get_db()
        db.execute('UPDATE api_settings SET last_tested=CURRENT_TIMESTAMP, test_status=? WHERE name=?', (status, name))
        db.commit()
        db.close()
        return jsonify({'success': success, 'message': msg})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@admin_bp.route('/api/set-default-model', methods=['POST'])
def set_default_model():
    data = request.get_json()
    model_id = data.get('model_id')
    db = get_db()
    db.execute('UPDATE ai_models SET is_default=0')
    db.execute('UPDATE ai_models SET is_default=1 WHERE model_id=?', (model_id,))
    db.commit()
    db.close()
    log_audit('model_change', 'ai_models', model_id)
    return jsonify({'success': True})

@admin_bp.route('/prompts', methods=['GET', 'POST'])
def prompts():
    site = get_site_settings()
    db = get_db()
    prompt_list = db.execute('SELECT * FROM prompt_templates ORDER BY type').fetchall()
    db.close()
    return render_template('admin/prompts.html', site=site, prompts=prompt_list)

@admin_bp.route('/api/prompts/<int:prompt_id>', methods=['PUT'])
def update_prompt(prompt_id):
    data = request.get_json()
    db = get_db()
    old = db.execute('SELECT content FROM prompt_templates WHERE id=?', (prompt_id,)).fetchone()
    db.execute('UPDATE prompt_templates SET content=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
               (data.get('content', ''), prompt_id))
    db.commit()
    db.close()
    log_audit('prompt_update', 'prompt_templates', prompt_id, old['content'][:100] if old else '', data.get('content', '')[:100])
    return jsonify({'success': True})

@admin_bp.route('/features', methods=['GET', 'POST'])
def features():
    site = get_site_settings()
    db = get_db()
    feature_list = db.execute('SELECT * FROM feature_toggles ORDER BY feature_name').fetchall()
    db.close()
    return render_template('admin/features.html', site=site, features=feature_list)

@admin_bp.route('/api/features/<int:feature_id>', methods=['PUT'])
def update_feature(feature_id):
    data = request.get_json()
    enabled = 1 if data.get('enabled') else 0
    db = get_db()
    feature = db.execute('SELECT * FROM feature_toggles WHERE id=?', (feature_id,)).fetchone()
    db.execute('UPDATE feature_toggles SET is_enabled=? WHERE id=?', (enabled, feature_id))
    db.commit()
    db.close()
    log_audit('feature_toggle', 'feature_toggles', feature['feature_name'] if feature else feature_id,
              str(not enabled), str(bool(enabled)))
    return jsonify({'success': True})

@admin_bp.route('/pwa-settings', methods=['GET', 'POST'])
def pwa_settings():
    site = get_site_settings()
    db = get_db()
    pwa = {r['key']: r['value'] for r in db.execute('SELECT key, value FROM pwa_settings').fetchall()}
    db.close()
    if request.method == 'POST':
        db = get_db()
        for key in ['app_name', 'short_name', 'theme_color', 'background_color', 'offline_mode', 'install_prompt']:
            if key in request.form:
                db.execute('INSERT OR REPLACE INTO pwa_settings (key, value) VALUES (?, ?)',
                           (key, request.form[key]))
        db.commit()
        db.close()
        log_audit('pwa_settings_update', 'pwa_settings')
        return redirect(url_for('admin.pwa_settings'))
    return render_template('admin/pwa_settings.html', site=site, pwa=pwa)

@admin_bp.route('/logs')
def logs():
    site = get_site_settings()
    db = get_db()
    level = request.args.get('level', '')
    source = request.args.get('source', '')
    query = 'SELECT * FROM system_logs'
    params = []
    conditions = []
    if level:
        conditions.append('level=?')
        params.append(level)
    if source:
        conditions.append('source LIKE ?')
        params.append(f'%{source}%')
    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)
    query += ' ORDER BY created_at DESC LIMIT 200'
    system_logs = db.execute(query, params).fetchall()
    audit_logs = db.execute('SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 100').fetchall()
    db.close()
    return render_template('admin/logs.html', site=site, system_logs=system_logs,
                           audit_logs=audit_logs, level=level, source=source)

@admin_bp.route('/backup', methods=['GET'])
def backup():
    site = get_site_settings()
    db = get_db()
    backups = db.execute('SELECT * FROM backups ORDER BY created_at DESC').fetchall()
    db.close()
    return render_template('admin/backup.html', site=site, backups=backups)

@admin_bp.route('/api/backup/create', methods=['POST'])
def create_backup():
    from config import Config
    backup_dir = 'backups'
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'litreview_backup_{timestamp}.db'
    filepath = os.path.join(backup_dir, filename)
    try:
        shutil.copy2(Config.DATABASE_PATH, filepath)
        file_size = os.path.getsize(filepath)
        db = get_db()
        db.execute('INSERT INTO backups (filename, file_path, file_size, backup_type) VALUES (?, ?, ?, ?)',
                   (filename, filepath, file_size, 'manual'))
        db.commit()
        db.close()
        log_audit('backup_created', 'backups', filename)
        return jsonify({'success': True, 'filename': filename})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@admin_bp.route('/api/backup/download/<filename>')
def download_backup(filename):
    import werkzeug.utils
    safe = werkzeug.utils.secure_filename(filename)
    path = os.path.join('backups', safe)
    if not os.path.exists(path):
        return 'Backup not found', 404
    return send_file(path, as_attachment=True, download_name=safe)

@admin_bp.route('/api/backup/delete/<int:backup_id>', methods=['DELETE'])
def delete_backup(backup_id):
    db = get_db()
    backup = db.execute('SELECT * FROM backups WHERE id=?', (backup_id,)).fetchone()
    if backup:
        file_deleted = True
        if os.path.exists(backup['file_path']):
            try:
                os.remove(backup['file_path'])
            except Exception as e:
                file_deleted = False
                db.execute('INSERT INTO system_logs (level, source, message) VALUES (?, ?, ?)',
                           ('WARN', 'admin:delete_backup', f"Could not delete file {backup['file_path']}: {e}"))
        if file_deleted:
            db.execute('DELETE FROM backups WHERE id=?', (backup_id,))
        db.commit()
        log_audit('backup_deleted', 'backups', backup_id)
    db.close()
    return jsonify({'success': True})

@admin_bp.route('/reports')
def reports():
    site = get_site_settings()
    db = get_db()
    status_filter = request.args.get('status', '')
    query = 'SELECT * FROM content_reports'
    params = []
    if status_filter:
        query += ' WHERE status=?'
        params.append(status_filter)
    query += ' ORDER BY created_at DESC'
    report_list = db.execute(query, params).fetchall()
    pending_count = db.execute("SELECT COUNT(*) as c FROM content_reports WHERE status='pending'").fetchone()['c']
    db.close()
    return render_template('admin/reports.html', site=site, reports=report_list,
                           pending_count=pending_count, status_filter=status_filter)

@admin_bp.route('/api/reports/<int:report_id>/approve', methods=['POST'])
def approve_report(report_id):
    db = get_db()
    db.execute("UPDATE content_reports SET status='approved', resolved_at=CURRENT_TIMESTAMP WHERE id=?", (report_id,))
    db.commit()
    db.close()
    log_audit('report_approved', 'content_reports', report_id)
    return jsonify({'success': True})

@admin_bp.route('/api/reports/<int:report_id>/dismiss', methods=['POST'])
def dismiss_report(report_id):
    db = get_db()
    db.execute("UPDATE content_reports SET status='dismissed', resolved_at=CURRENT_TIMESTAMP WHERE id=?", (report_id,))
    db.commit()
    db.close()
    log_audit('report_dismissed', 'content_reports', report_id)
    return jsonify({'success': True})

@admin_bp.route('/api/reports/<int:report_id>/delete-content', methods=['POST'])
def delete_reported_content(report_id):
    db = get_db()
    report = db.execute('SELECT * FROM content_reports WHERE id=?', (report_id,)).fetchone()
    if not report:
        db.close()
        return jsonify({'success': False, 'error': 'Report not found'})
    content_type = report['content_type']
    content_id = report['content_id']
    deleted = False
    try:
        if content_type == 'review' and content_id:
            db.execute('DELETE FROM literature_reviews WHERE id=?', (content_id,))
            deleted = True
        elif content_type == 'chat' and content_id:
            db.execute('DELETE FROM chat_messages WHERE session_id=?', (content_id,))
            db.execute('DELETE FROM chat_sessions WHERE id=?', (content_id,))
            deleted = True
        db.execute("UPDATE content_reports SET status='approved', resolved_at=CURRENT_TIMESTAMP WHERE id=?", (report_id,))
        db.commit()
        log_audit('reported_content_deleted', content_type, content_id)
    except Exception as e:
        db.close()
        return jsonify({'success': False, 'error': str(e)})
    db.close()
    return jsonify({'success': True, 'deleted': deleted})

@admin_bp.route('/api/cleanup/run', methods=['POST'])
def run_cleanup():
    from app import _run_cleanup
    try:
        _run_cleanup()
        db = get_db()
        last = db.execute(
            "SELECT message, details FROM system_logs WHERE source='cleanup' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        db.close()
        log_audit('manual_cleanup', 'files', 'uploads+exports')
        return jsonify({'success': True, 'message': last['message'], 'details': last['details']})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@admin_bp.route('/api/analytics')
def analytics_data():
    db = get_db()
    data = {
        'papers_by_source': [dict(r) for r in db.execute('SELECT source, COUNT(*) as count FROM papers GROUP BY source').fetchall()],
        'papers_by_year': [dict(r) for r in db.execute('SELECT year, COUNT(*) as count FROM papers WHERE year IS NOT NULL GROUP BY year ORDER BY year').fetchall()],
        'reviews_over_time': [dict(r) for r in db.execute("SELECT DATE(created_at) as date, COUNT(*) as count FROM literature_reviews GROUP BY DATE(created_at) ORDER BY date DESC LIMIT 30").fetchall()],
        'ai_usage': [dict(r) for r in db.execute("SELECT source, COUNT(*) as count FROM system_logs WHERE source LIKE 'ai:%' GROUP BY source").fetchall()],
    }
    db.close()
    return jsonify(data)
