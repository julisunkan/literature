from flask import Blueprint, render_template, request, jsonify, redirect, url_for, send_file, current_app
from models import get_db
import json, os

main_bp = Blueprint('main', __name__)

def get_site_settings():
    db = get_db()
    rows = db.execute('SELECT key, value FROM site_settings').fetchall()
    db.close()
    return {r['key']: r['value'] for r in rows}

def get_notifications():
    db = get_db()
    rows = db.execute('SELECT * FROM notifications WHERE is_read=0 ORDER BY created_at DESC LIMIT 10').fetchall()
    db.close()
    return [dict(r) for r in rows]

@main_bp.route('/')
def index():
    site = get_site_settings()
    db = get_db()
    stats = {
        'papers': db.execute('SELECT COUNT(*) as c FROM papers').fetchone()['c'],
        'reviews': db.execute('SELECT COUNT(*) as c FROM literature_reviews').fetchone()['c'],
        'uploads': db.execute('SELECT COUNT(*) as c FROM paper_files').fetchone()['c'],
    }
    recent_reviews = db.execute('SELECT * FROM literature_reviews ORDER BY created_at DESC LIMIT 5').fetchall()
    db.close()
    return render_template('index.html', site=site, stats=stats,
                           recent_reviews=recent_reviews, notifications=get_notifications())

@main_bp.route('/search')
def search():
    site = get_site_settings()
    query = request.args.get('q', '')
    sources = request.args.getlist('sources') or ['openalex', 'semantic_scholar', 'crossref', 'pubmed', 'arxiv']
    year_from = request.args.get('year_from', type=int)
    year_to = request.args.get('year_to', type=int)
    sort_by = request.args.get('sort', 'relevance')
    results = []
    if query:
        from services.search_service import search_all
        results = search_all(query, sources, year_from, year_to, limit=15)
        if sort_by == 'year':
            results.sort(key=lambda x: x.get('year') or 0, reverse=True)
        elif sort_by == 'citations':
            results.sort(key=lambda x: x.get('citations_count') or 0, reverse=True)
        db = get_db()
        db.execute('INSERT INTO activity_logs (action, details) VALUES (?, ?)',
                   ('search', f'Query: {query}, Results: {len(results)}'))
        db.commit()
        db.close()
    return render_template('search.html', site=site, query=query, results=results,
                           sources=sources, year_from=year_from, year_to=year_to,
                           sort_by=sort_by, notifications=get_notifications())

@main_bp.route('/papers')
def papers():
    site = get_site_settings()
    db = get_db()
    page = request.args.get('page', 1, type=int)
    per_page = 20
    offset = (page - 1) * per_page
    total = db.execute('SELECT COUNT(*) as c FROM papers').fetchone()['c']
    papers_list = db.execute('SELECT * FROM papers ORDER BY created_at DESC LIMIT ? OFFSET ?',
                             (per_page, offset)).fetchall()
    db.close()
    total_pages = (total + per_page - 1) // per_page
    return render_template('papers.html', site=site, papers=papers_list,
                           page=page, total_pages=total_pages, total=total,
                           notifications=get_notifications())

@main_bp.route('/papers/<int:paper_id>')
def paper_detail(paper_id):
    site = get_site_settings()
    db = get_db()
    paper = db.execute('SELECT * FROM papers WHERE id=?', (paper_id,)).fetchone()
    if not paper:
        db.close()
        return redirect(url_for('main.papers'))
    notes = db.execute('SELECT * FROM paper_notes WHERE paper_id=? ORDER BY created_at DESC', (paper_id,)).fetchall()
    files = db.execute('SELECT * FROM paper_files WHERE paper_id=?', (paper_id,)).fetchall()
    citations_saved = db.execute('SELECT * FROM citations WHERE paper_id=?', (paper_id,)).fetchall()
    db.close()
    return render_template('paper_detail.html', site=site, paper=paper,
                           notes=notes, files=files, citations_saved=citations_saved,
                           notifications=get_notifications())

@main_bp.route('/api/papers/save', methods=['POST'])
def save_paper_api():
    from services.search_service import save_paper
    data = request.get_json()
    paper_id = save_paper(data)
    return jsonify({'success': True, 'paper_id': paper_id})

@main_bp.route('/api/papers/<int:paper_id>/note', methods=['POST'])
def save_note(paper_id):
    data = request.get_json()
    db = get_db()
    existing = db.execute('SELECT id FROM paper_notes WHERE paper_id=? AND id=?',
                          (paper_id, data.get('note_id', 0))).fetchone()
    if existing:
        db.execute('UPDATE paper_notes SET content=?, tags=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
                   (data.get('content', ''), data.get('tags', ''), existing['id']))
    else:
        db.execute('INSERT INTO paper_notes (paper_id, content, tags) VALUES (?, ?, ?)',
                   (paper_id, data.get('content', ''), data.get('tags', '')))
    db.commit()
    db.close()
    return jsonify({'success': True})

@main_bp.route('/api/papers/<int:paper_id>/note/<int:note_id>', methods=['DELETE'])
def delete_note(paper_id, note_id):
    db = get_db()
    db.execute('DELETE FROM paper_notes WHERE id=? AND paper_id=?', (note_id, paper_id))
    db.commit()
    db.close()
    return jsonify({'success': True})

@main_bp.route('/api/notifications/read', methods=['POST'])
def mark_notifications_read():
    db = get_db()
    db.execute('UPDATE notifications SET is_read=1')
    db.commit()
    db.close()
    return jsonify({'success': True})

@main_bp.route('/upload', methods=['GET', 'POST'])
def upload():
    site = get_site_settings()
    db = get_db()
    feature = db.execute("SELECT is_enabled FROM feature_toggles WHERE feature_name='pdf_upload'").fetchone()
    db.close()
    if feature and not feature['is_enabled']:
        return render_template('feature_disabled.html', site=site, feature='PDF Upload')

    if request.method == 'POST':
        from services.pdf_service import process_upload, allowed_file
        import werkzeug.utils
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        file = request.files['file']
        if not file.filename or not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Only PDF, TXT, DOC, DOCX allowed.'}), 400
        from config import Config
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        safe_name = werkzeug.utils.secure_filename(file.filename)
        import time
        unique_name = f"{int(time.time())}_{safe_name}"
        file_path = os.path.join(Config.UPLOAD_FOLDER, unique_name)
        try:
            file.save(file_path)
        except OSError as e:
            return jsonify({'error': f'Could not save file: {e}'}), 500
        paper_id = request.form.get('paper_id', type=int)
        db = get_db()
        db.execute('INSERT INTO uploads (filename, original_name, file_size, status, paper_id) VALUES (?, ?, ?, ?, ?)',
                   (unique_name, file.filename, os.path.getsize(file_path), 'processing', paper_id))
        db.commit()
        db.close()
        result = process_upload(file_path, file.filename, paper_id)
        return jsonify(result)

    return render_template('upload.html', site=site, notifications=get_notifications())

@main_bp.route('/dashboard')
def dashboard():
    site = get_site_settings()
    db = get_db()
    stats = {
        'papers': db.execute('SELECT COUNT(*) as c FROM papers').fetchone()['c'],
        'reviews': db.execute('SELECT COUNT(*) as c FROM literature_reviews').fetchone()['c'],
        'uploads': db.execute('SELECT COUNT(*) as c FROM paper_files').fetchone()['c'],
        'notes': db.execute('SELECT COUNT(*) as c FROM paper_notes').fetchone()['c'],
    }
    recent_papers = db.execute('SELECT * FROM papers ORDER BY created_at DESC LIMIT 5').fetchall()
    recent_reviews = db.execute('SELECT * FROM literature_reviews ORDER BY created_at DESC LIMIT 5').fetchall()
    year_dist = db.execute('''SELECT year, COUNT(*) as count FROM papers
                               WHERE year IS NOT NULL GROUP BY year ORDER BY year DESC LIMIT 20''').fetchall()
    source_dist = db.execute('SELECT source, COUNT(*) as count FROM papers GROUP BY source').fetchall()
    db.close()
    return render_template('dashboard.html', site=site, stats=stats,
                           recent_papers=recent_papers, recent_reviews=recent_reviews,
                           year_dist=[dict(r) for r in year_dist],
                           source_dist=[dict(r) for r in source_dist],
                           notifications=get_notifications())

@main_bp.route('/reviews')
def reviews():
    site = get_site_settings()
    db = get_db()
    reviews_list = db.execute('SELECT * FROM literature_reviews ORDER BY created_at DESC').fetchall()
    db.close()
    return render_template('reviews.html', site=site, reviews=reviews_list, notifications=get_notifications())

@main_bp.route('/reviews/<int:review_id>')
def review_detail(review_id):
    site = get_site_settings()
    db = get_db()
    review = db.execute('SELECT * FROM literature_reviews WHERE id=?', (review_id,)).fetchone()
    if not review:
        db.close()
        return redirect(url_for('main.reviews'))
    versions = db.execute('SELECT * FROM review_versions WHERE review_id=? ORDER BY version_number DESC',
                          (review_id,)).fetchall()
    paper_ids = json.loads(review['paper_ids']) if review['paper_ids'] else []
    papers = []
    if paper_ids:
        placeholders = ','.join('?' * len(paper_ids))
        papers = db.execute(f'SELECT * FROM papers WHERE id IN ({placeholders})', paper_ids).fetchall()
    db.close()
    return render_template('review_detail.html', site=site, review=review,
                           versions=versions, papers=papers, notifications=get_notifications())

@main_bp.route('/matrix')
def matrix():
    site = get_site_settings()
    db = get_db()
    papers_list = db.execute('SELECT * FROM papers ORDER BY year DESC').fetchall()
    db.close()
    return render_template('matrix.html', site=site, papers=papers_list, notifications=get_notifications())

@main_bp.route('/visualizations')
def visualizations():
    site = get_site_settings()
    db = get_db()
    year_dist = db.execute('''SELECT year, COUNT(*) as count FROM papers
                               WHERE year IS NOT NULL GROUP BY year ORDER BY year''').fetchall()
    source_dist = db.execute('SELECT source, COUNT(*) as count FROM papers GROUP BY source').fetchall()
    top_keywords = {}
    kw_rows = db.execute('SELECT keywords FROM papers WHERE keywords IS NOT NULL AND keywords != ""').fetchall()
    for row in kw_rows:
        for kw in (row['keywords'] or '').split(','):
            kw = kw.strip().lower()
            if kw and len(kw) > 2:
                top_keywords[kw] = top_keywords.get(kw, 0) + 1
    top_kw = sorted(top_keywords.items(), key=lambda x: x[1], reverse=True)[:20]
    db.close()
    return render_template('visualizations.html', site=site,
                           year_dist=[dict(r) for r in year_dist],
                           source_dist=[dict(r) for r in source_dist],
                           top_keywords=top_kw,
                           notifications=get_notifications())

@main_bp.route('/knowledge-graph')
def knowledge_graph():
    site = get_site_settings()
    db = get_db()
    feature = db.execute("SELECT is_enabled FROM feature_toggles WHERE feature_name='knowledge_graph'").fetchone()
    if feature and not feature['is_enabled']:
        db.close()
        return render_template('feature_disabled.html', site=site, feature='Knowledge Graph')
    papers = db.execute('SELECT id, title, authors, year, keywords FROM papers LIMIT 100').fetchall()
    db.close()
    nodes = []
    links = []
    paper_map = {}
    for p in papers:
        paper_map[p['id']] = p['title']
        nodes.append({'id': f'paper_{p["id"]}', 'label': (p['title'] or '')[:40],
                      'type': 'paper', 'year': p['year']})
        if p['keywords']:
            for kw in (p['keywords'] or '').split(',')[:3]:
                kw = kw.strip()
                if kw:
                    kw_id = f'kw_{kw.lower().replace(" ", "_")}'
                    if not any(n['id'] == kw_id for n in nodes):
                        nodes.append({'id': kw_id, 'label': kw, 'type': 'keyword'})
                    links.append({'source': f'paper_{p["id"]}', 'target': kw_id})
    graph_data = json.dumps({'nodes': nodes, 'links': links})
    return render_template('knowledge_graph.html', site=site, graph_data=graph_data,
                           notifications=get_notifications())

@main_bp.route('/prisma')
def prisma():
    site = get_site_settings()
    db = get_db()
    feature = db.execute("SELECT is_enabled FROM feature_toggles WHERE feature_name='prisma_mode'").fetchone()
    if feature and not feature['is_enabled']:
        db.close()
        return render_template('feature_disabled.html', site=site, feature='PRISMA Mode')
    total_papers = db.execute('SELECT COUNT(*) as c FROM papers').fetchone()['c']
    db.close()
    return render_template('prisma.html', site=site, total_papers=total_papers,
                           notifications=get_notifications())

@main_bp.route('/api/report-content', methods=['POST'])
def report_content():
    data = request.get_json()
    content_type = data.get('content_type', '').strip()
    content_id = data.get('content_id')
    content_title = data.get('content_title', '')[:200]
    content_snippet = data.get('content_snippet', '')[:500]
    reason = data.get('reason', '').strip()
    notes = data.get('notes', '')[:1000]
    if not content_type or not reason:
        return jsonify({'success': False, 'error': 'Missing required fields'})
    db = get_db()
    db.execute(
        'INSERT INTO content_reports (content_type, content_id, content_title, content_snippet, reason, notes) VALUES (?, ?, ?, ?, ?, ?)',
        (content_type, content_id, content_title, content_snippet, reason, notes)
    )
    db.execute('INSERT INTO notifications (type, title, message) VALUES (?, ?, ?)',
               ('report', 'Content Reported', f'A {content_type} was reported: {reason}'))
    db.commit()
    db.close()
    return jsonify({'success': True})

@main_bp.route('/offline')
def offline():
    return render_template('offline.html')
