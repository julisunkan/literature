from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from models import get_db
import json

ai_bp = Blueprint('ai', __name__, url_prefix='/ai')

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

@ai_bp.route('/generate-review', methods=['GET', 'POST'])
def generate_review():
    site = get_site_settings()
    db = get_db()
    papers_list = db.execute('SELECT id, title, authors, year, abstract FROM papers ORDER BY created_at DESC').fetchall()
    db.close()
    return render_template('ai/generate_review.html', site=site, papers=papers_list,
                           notifications=get_notifications())

@ai_bp.route('/api/generate-review', methods=['POST'])
def api_generate_review():
    data = request.get_json()
    topic = data.get('topic', '')
    paper_ids = data.get('paper_ids', [])
    if not topic:
        return jsonify({'error': 'Topic is required'}), 400
    if not paper_ids:
        return jsonify({'error': 'Select at least one paper'}), 400
    try:
        from services.ai_service import generate_literature_review
        db = get_db()
        placeholders = ','.join('?' * len(paper_ids))
        papers = db.execute(f'SELECT * FROM papers WHERE id IN ({placeholders})', paper_ids).fetchall()
        db.close()
        papers_data = [dict(p) for p in papers]
        result = generate_literature_review(topic, papers_data)
        parts = _parse_review_sections(result)
        db = get_db()
        cur = db.execute('''INSERT INTO literature_reviews
            (title, topic, introduction, thematic_analysis, research_gaps, future_directions, conclusion, paper_ids, status, word_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (f'Literature Review: {topic}', topic,
             parts.get('introduction', ''), parts.get('thematic_analysis', ''),
             parts.get('research_gaps', ''), parts.get('future_directions', ''),
             parts.get('conclusion', ''), json.dumps(paper_ids), 'completed',
             len(result.split())))
        review_id = cur.lastrowid
        db.execute('INSERT INTO notifications (type, title, message) VALUES (?, ?, ?)',
                   ('review', 'Review Generated', f'Literature review for "{topic}" is ready.'))
        db.execute('INSERT INTO activity_logs (action, details) VALUES (?, ?)',
                   ('review_generated', f'Topic: {topic}'))
        db.commit()
        db.close()
        return jsonify({'success': True, 'review_id': review_id, 'content': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@ai_bp.route('/api/summarize', methods=['POST'])
def api_summarize():
    data = request.get_json()
    abstract = data.get('abstract', '') or data.get('text', '')
    paper_id = data.get('paper_id')
    if not abstract:
        return jsonify({'error': 'No text provided'}), 400
    try:
        from services.ai_service import summarize_abstract
        result = summarize_abstract(abstract)
        return jsonify({'success': True, 'summary': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@ai_bp.route('/api/research-questions', methods=['POST'])
def api_research_questions():
    data = request.get_json()
    topic = data.get('topic', '')
    context = data.get('context', '')
    if not topic:
        return jsonify({'error': 'Topic is required'}), 400
    try:
        from services.ai_service import generate_research_questions
        result = generate_research_questions(topic, context)
        return jsonify({'success': True, 'questions': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@ai_bp.route('/api/detect-gaps', methods=['POST'])
def api_detect_gaps():
    data = request.get_json()
    paper_ids = data.get('paper_ids', [])
    if not paper_ids:
        return jsonify({'error': 'No papers selected'}), 400
    try:
        from services.ai_service import detect_gaps
        db = get_db()
        placeholders = ','.join('?' * len(paper_ids))
        papers = db.execute(f'SELECT * FROM papers WHERE id IN ({placeholders})', paper_ids).fetchall()
        db.close()
        result = detect_gaps([dict(p) for p in papers])
        return jsonify({'success': True, 'gaps': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@ai_bp.route('/api/thematic-analysis', methods=['POST'])
def api_thematic_analysis():
    data = request.get_json()
    paper_ids = data.get('paper_ids', [])
    if not paper_ids:
        return jsonify({'error': 'No papers selected'}), 400
    try:
        from services.ai_service import thematic_analysis
        db = get_db()
        placeholders = ','.join('?' * len(paper_ids))
        papers = db.execute(f'SELECT * FROM papers WHERE id IN ({placeholders})', paper_ids).fetchall()
        db.close()
        result = thematic_analysis([dict(p) for p in papers])
        return jsonify({'success': True, 'analysis': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@ai_bp.route('/api/contradictions', methods=['POST'])
def api_contradictions():
    data = request.get_json()
    paper_ids = data.get('paper_ids', [])
    if not paper_ids:
        return jsonify({'error': 'No papers selected'}), 400
    try:
        from services.ai_service import detect_contradictions
        db = get_db()
        placeholders = ','.join('?' * len(paper_ids))
        papers = db.execute(f'SELECT * FROM papers WHERE id IN ({placeholders})', paper_ids).fetchall()
        db.close()
        result = detect_contradictions([dict(p) for p in papers])
        return jsonify({'success': True, 'contradictions': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@ai_bp.route('/chat')
def chat():
    site = get_site_settings()
    db = get_db()
    feature = db.execute("SELECT is_enabled FROM feature_toggles WHERE feature_name='ai_chat'").fetchone()
    if feature and not feature['is_enabled']:
        db.close()
        return render_template('feature_disabled.html', site=site, feature='AI Chat')
    sessions = db.execute('SELECT * FROM chat_sessions ORDER BY updated_at DESC LIMIT 20').fetchall()
    papers_list = db.execute('SELECT id, title FROM papers ORDER BY created_at DESC LIMIT 50').fetchall()
    db.close()
    return render_template('ai/chat.html', site=site, sessions=sessions,
                           papers=papers_list, notifications=get_notifications())

@ai_bp.route('/api/chat', methods=['POST'])
def api_chat():
    data = request.get_json()
    question = data.get('question', '')
    session_id = data.get('session_id')
    paper_ids = data.get('paper_ids', [])
    if not question:
        return jsonify({'error': 'Question is required'}), 400
    try:
        context = ''
        if paper_ids:
            db = get_db()
            placeholders = ','.join('?' * len(paper_ids))
            papers = db.execute(f'SELECT title, abstract, full_text FROM papers WHERE id IN ({placeholders})', paper_ids).fetchall()
            db.close()
            context = '\n\n'.join([
                f"Title: {p['title']}\nAbstract: {p['abstract'] or ''}\n{(p['full_text'] or '')[:500]}"
                for p in papers
            ])

        db = get_db()
        if not session_id:
            cur = db.execute('INSERT INTO chat_sessions (title, context_type, context_ids) VALUES (?, ?, ?)',
                             (question[:50], 'papers', json.dumps(paper_ids)))
            session_id = cur.lastrowid
        else:
            history = db.execute('SELECT role, content FROM chat_messages WHERE session_id=? ORDER BY created_at DESC LIMIT 6',
                                 (session_id,)).fetchall()
            if history:
                history_text = '\n'.join([f"{m['role'].upper()}: {m['content']}" for m in reversed(history)])
                context = f"Conversation history:\n{history_text}\n\nPaper context:\n{context}"

        db.execute('INSERT INTO chat_messages (session_id, role, content) VALUES (?, ?, ?)',
                   (session_id, 'user', question))
        db.commit()

        from services.ai_service import chat_with_papers
        answer = chat_with_papers(question, context)
        db.execute('INSERT INTO chat_messages (session_id, role, content) VALUES (?, ?, ?)',
                   (session_id, 'assistant', answer))
        db.execute('UPDATE chat_sessions SET updated_at=CURRENT_TIMESTAMP WHERE id=?', (session_id,))
        db.commit()
        db.close()
        return jsonify({'success': True, 'answer': answer, 'session_id': session_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@ai_bp.route('/api/methodology', methods=['POST'])
def api_methodology():
    data = request.get_json()
    paper_id = data.get('paper_id')
    text = data.get('text', '')
    if not paper_id and not text:
        return jsonify({'error': 'Paper ID or text required'}), 400
    try:
        if paper_id:
            db = get_db()
            pf = db.execute('SELECT extracted_text FROM paper_files WHERE paper_id=? LIMIT 1', (paper_id,)).fetchone()
            paper = db.execute('SELECT abstract FROM papers WHERE id=?', (paper_id,)).fetchone()
            db.close()
            text = (pf['extracted_text'] if pf else '') or (paper['abstract'] if paper else '')
        from services.ai_service import extract_methodology
        result = extract_methodology(text)
        return jsonify({'success': True, 'methodology': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def _parse_review_sections(text):
    import re
    sections = {}
    patterns = {
        'introduction': r'(?i)##?\s*introduction\s*\n+(.*?)(?=##?\s*\w|\Z)',
        'thematic_analysis': r'(?i)##?\s*thematic\s+analysis\s*\n+(.*?)(?=##?\s*\w|\Z)',
        'research_gaps': r'(?i)##?\s*research\s+gaps?\s*\n+(.*?)(?=##?\s*\w|\Z)',
        'future_directions': r'(?i)##?\s*future\s+directions?\s*\n+(.*?)(?=##?\s*\w|\Z)',
        'conclusion': r'(?i)##?\s*conclusion\s*\n+(.*?)(?=##?\s*\w|\Z)',
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.DOTALL)
        sections[key] = match.group(1).strip() if match else ''
    if not any(sections.values()):
        sections['introduction'] = text
    return sections
