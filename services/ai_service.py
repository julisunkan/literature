import os
import json
import requests
from models import get_db

def get_ai_settings():
    db = get_db()
    settings = {}
    rows = db.execute('SELECT name, key_value, is_enabled FROM api_settings').fetchall()
    for r in rows:
        settings[r['name']] = {'value': r['key_value'], 'enabled': r['is_enabled']}
    model_row = db.execute('SELECT model_id, provider FROM ai_models WHERE is_default=1 LIMIT 1').fetchone()
    db.close()
    settings['default_model'] = model_row['model_id'] if model_row else 'llama3-70b-8192'
    settings['default_provider'] = model_row['provider'] if model_row else 'groq'
    return settings

def get_prompt(name):
    db = get_db()
    row = db.execute('SELECT content FROM prompt_templates WHERE name=?', (name,)).fetchone()
    db.close()
    return row['content'] if row else ''

def log_ai_request(provider, model, prompt_type, status, details=''):
    db = get_db()
    db.execute('INSERT INTO system_logs (level, source, message, details) VALUES (?, ?, ?, ?)',
               ('INFO', f'ai:{provider}', f'{prompt_type} request - {status}', details))
    db.commit()
    db.close()

def call_groq(prompt, system_msg='You are a helpful academic research assistant.', model=None):
    from config import Config
    db = get_db()
    key_row = db.execute("SELECT key_value FROM api_settings WHERE name='groq_api_key'").fetchone()
    db.close()
    api_key = (key_row['key_value'] if key_row else '') or Config.GROQ_API_KEY
    if not api_key:
        raise ValueError('Groq API key not configured. Please add it in Admin > API Management.')

    settings = get_ai_settings()
    use_model = model or settings.get('default_model', 'llama3-70b-8192')

    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    payload = {
        'model': use_model,
        'messages': [
            {'role': 'system', 'content': system_msg},
            {'role': 'user', 'content': prompt}
        ],
        'temperature': 0.7,
        'max_tokens': 4096
    }
    resp = requests.post('https://api.groq.com/openai/v1/chat/completions',
                         headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data['choices'][0]['message']['content']

def call_openrouter(prompt, system_msg='You are a helpful academic research assistant.', model='openai/gpt-3.5-turbo'):
    from config import Config
    db = get_db()
    key_row = db.execute("SELECT key_value FROM api_settings WHERE name='openrouter_api_key'").fetchone()
    db.close()
    api_key = (key_row['key_value'] if key_row else '') or Config.OPENROUTER_API_KEY
    if not api_key:
        raise ValueError('OpenRouter API key not configured.')

    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json',
               'HTTP-Referer': 'https://litreview.app', 'X-Title': 'LitReview'}
    payload = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': system_msg},
            {'role': 'user', 'content': prompt}
        ]
    }
    resp = requests.post('https://openrouter.ai/api/v1/chat/completions',
                         headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data['choices'][0]['message']['content']

def call_gemini(prompt):
    from config import Config
    db = get_db()
    key_row = db.execute("SELECT key_value FROM api_settings WHERE name='gemini_api_key'").fetchone()
    db.close()
    api_key = (key_row['key_value'] if key_row else '') or Config.GEMINI_API_KEY
    if not api_key:
        raise ValueError('Gemini API key not configured.')

    url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={api_key}'
    payload = {'contents': [{'parts': [{'text': prompt}]}]}
    resp = requests.post(url, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data['candidates'][0]['content']['parts'][0]['text']

def call_ollama(prompt, model='llama3'):
    from config import Config
    db = get_db()
    url_row = db.execute("SELECT key_value FROM api_settings WHERE name='ollama_url'").fetchone()
    db.close()
    base_url = (url_row['key_value'] if url_row else '') or Config.OLLAMA_URL
    url = f'{base_url}/api/generate'
    payload = {'model': model, 'prompt': prompt, 'stream': False}
    resp = requests.post(url, json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json().get('response', '')

def call_ai(prompt, system_msg='You are a helpful academic research assistant.', prompt_type='general'):
    settings = get_ai_settings()
    provider = settings.get('default_provider', 'groq')

    providers_order = [provider]
    for fb in ['groq', 'openrouter', 'gemini', 'ollama']:
        if fb not in providers_order:
            providers_order.append(fb)

    last_error = None
    for p in providers_order:
        try:
            if p == 'groq':
                result = call_groq(prompt, system_msg)
            elif p == 'openrouter':
                result = call_openrouter(prompt, system_msg)
            elif p == 'gemini':
                result = call_gemini(prompt)
            elif p == 'ollama':
                result = call_ollama(prompt)
            else:
                continue
            log_ai_request(p, settings.get('default_model', ''), prompt_type, 'success')
            return result
        except Exception as e:
            last_error = e
            log_ai_request(p, '', prompt_type, 'error', str(e))
            continue

    raise Exception(f'All AI providers failed. Last error: {last_error}')

def generate_literature_review(topic, papers):
    template = get_prompt('literature_review')
    papers_text = '\n\n'.join([
        f"Title: {p.get('title','')}\nAuthors: {p.get('authors','')}\nYear: {p.get('year','')}\nAbstract: {p.get('abstract','')}"
        for p in papers
    ])
    prompt = template.format(topic=topic, papers=papers_text)
    return call_ai(prompt, prompt_type='literature_review')

def summarize_abstract(abstract):
    template = get_prompt('summarize_abstract')
    prompt = template.format(abstract=abstract)
    return call_ai(prompt, prompt_type='summarization')

def generate_research_questions(topic, context=''):
    template = get_prompt('research_questions')
    prompt = template.format(topic=topic, context=context)
    return call_ai(prompt, prompt_type='research_questions')

def detect_gaps(papers):
    template = get_prompt('gap_analysis')
    papers_text = '\n\n'.join([
        f"Title: {p.get('title','')}\nAbstract: {p.get('abstract','')}"
        for p in papers
    ])
    prompt = template.format(papers=papers_text)
    return call_ai(prompt, prompt_type='gap_analysis')

def thematic_analysis(papers):
    template = get_prompt('thematic_analysis')
    papers_text = '\n\n'.join([
        f"Title: {p.get('title','')}\nAbstract: {p.get('abstract','')}"
        for p in papers
    ])
    prompt = template.format(papers=papers_text)
    return call_ai(prompt, prompt_type='thematic_analysis')

def detect_contradictions(papers):
    template = get_prompt('contradiction_detection')
    papers_text = '\n\n'.join([
        f"Title: {p.get('title','')}\nYear: {p.get('year','')}\nAbstract: {p.get('abstract','')}"
        for p in papers
    ])
    prompt = template.format(papers=papers_text)
    return call_ai(prompt, prompt_type='contradiction')

def extract_methodology(paper_text):
    template = get_prompt('methodology_extraction')
    prompt = template.format(paper=paper_text[:3000])
    return call_ai(prompt, prompt_type='methodology')

def chat_with_papers(question, context):
    template = get_prompt('chat_rag')
    prompt = template.format(context=context[:4000], question=question)
    return call_ai(prompt, prompt_type='chat')
