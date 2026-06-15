import sqlite3
import os
from config import Config

def get_db():
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.executescript('''
        CREATE TABLE IF NOT EXISTS papers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            authors TEXT,
            abstract TEXT,
            year INTEGER,
            doi TEXT,
            url TEXT,
            journal TEXT,
            citations_count INTEGER DEFAULT 0,
            source TEXT,
            keywords TEXT,
            full_text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS paper_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paper_id INTEGER,
            filename TEXT,
            original_name TEXT,
            file_path TEXT,
            file_size INTEGER,
            extracted_text TEXT,
            sections TEXT,
            ocr_used INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (paper_id) REFERENCES papers(id)
        );

        CREATE TABLE IF NOT EXISTS paper_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paper_id INTEGER,
            content TEXT,
            tags TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (paper_id) REFERENCES papers(id)
        );

        CREATE TABLE IF NOT EXISTS literature_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            topic TEXT,
            introduction TEXT,
            thematic_analysis TEXT,
            research_gaps TEXT,
            future_directions TEXT,
            conclusion TEXT,
            paper_ids TEXT,
            status TEXT DEFAULT 'draft',
            word_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS review_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            review_id INTEGER,
            version_number INTEGER,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (review_id) REFERENCES literature_reviews(id)
        );

        CREATE TABLE IF NOT EXISTS citations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paper_id INTEGER,
            style TEXT,
            citation_text TEXT,
            in_text TEXT,
            bibtex TEXT,
            ris TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (paper_id) REFERENCES papers(id)
        );

        CREATE TABLE IF NOT EXISTS themes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            review_id INTEGER,
            name TEXT,
            description TEXT,
            paper_ids TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (review_id) REFERENCES literature_reviews(id)
        );

        CREATE TABLE IF NOT EXISTS research_gaps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            review_id INTEGER,
            gap_type TEXT,
            description TEXT,
            evidence TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (review_id) REFERENCES literature_reviews(id)
        );

        CREATE TABLE IF NOT EXISTS chat_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            context_type TEXT DEFAULT 'general',
            context_ids TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            role TEXT,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            title TEXT,
            message TEXT,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS api_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            key_value TEXT,
            is_enabled INTEGER DEFAULT 1,
            provider_type TEXT,
            last_tested TIMESTAMP,
            test_status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS ai_models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT,
            model_id TEXT,
            display_name TEXT,
            is_default INTEGER DEFAULT 0,
            is_enabled INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS prompt_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            type TEXT,
            content TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS feature_toggles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            feature_name TEXT UNIQUE,
            is_enabled INTEGER DEFAULT 1,
            description TEXT
        );

        CREATE TABLE IF NOT EXISTS site_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT,
            details TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_action TEXT,
            entity_type TEXT,
            entity_id TEXT,
            old_value TEXT,
            new_value TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS system_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level TEXT,
            source TEXT,
            message TEXT,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS exports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            filename TEXT,
            file_path TEXT,
            format TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS uploads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            original_name TEXT,
            file_size INTEGER,
            status TEXT DEFAULT 'processing',
            paper_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS backups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            file_path TEXT,
            file_size INTEGER,
            backup_type TEXT DEFAULT 'manual',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS pwa_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS content_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_type TEXT NOT NULL,
            content_id INTEGER,
            content_title TEXT,
            content_snippet TEXT,
            reason TEXT NOT NULL,
            notes TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP
        );
    ''')

    _seed_defaults(c)
    conn.commit()
    conn.close()

def _seed_defaults(c):
    site_defaults = [
        ('site_name', 'Literature Review Generator'),
        ('site_tagline', 'AI-Powered Academic Research Assistant'),
        ('footer_text', '© 2024 Literature Review Generator. Free for academic use.'),
        ('contact_email', 'admin@litreview.app'),
        ('about_text', 'An AI-powered tool for generating comprehensive literature reviews.'),
        ('privacy_policy', 'We respect your privacy. No personal data is collected.'),
        ('terms', 'This tool is provided free for academic and research purposes.'),
    ]
    for key, val in site_defaults:
        c.execute('INSERT OR IGNORE INTO site_settings (key, value) VALUES (?, ?)', (key, val))

    prompts = [
        ('literature_review', 'literature_review',
         'You are an expert academic researcher. Generate a comprehensive literature review on the topic "{topic}" based on the following papers:\n\n{papers}\n\nStructure the review with: Introduction, Thematic Analysis, Research Gaps, Future Directions, and Conclusion. Use academic writing style.'),
        ('summarize_abstract', 'summarization',
         'Analyze this academic paper abstract and extract: 1) Objective, 2) Methodology, 3) Key Findings, 4) Limitations.\n\nAbstract: {abstract}'),
        ('research_questions', 'question_generation',
         'Based on this topic and papers, generate: 1) Main research question, 2) 3-5 sub-questions, 3) 2-3 hypotheses.\n\nTopic: {topic}\nContext: {context}'),
        ('gap_analysis', 'gap_analysis',
         'Analyze these research papers and identify: 1) Underexplored areas, 2) Contradictions between studies, 3) Geographic gaps, 4) Methodological gaps.\n\nPapers: {papers}'),
        ('thematic_analysis', 'thematic_analysis',
         'Cluster these papers into research themes. For each theme provide: theme name, key papers, main argument.\n\nPapers: {papers}'),
        ('contradiction_detection', 'contradiction',
         'Identify contradicting findings across these papers. For each contradiction: describe the conflict, cite the papers, suggest possible explanations.\n\nPapers: {papers}'),
        ('methodology_extraction', 'methodology',
         'Extract methodology details from this paper: sample size, research design, data collection method, analysis approach.\n\nPaper: {paper}'),
        ('chat_rag', 'chat',
         'You are a research assistant helping with academic papers. Answer based on the provided context.\n\nContext: {context}\n\nQuestion: {question}'),
    ]
    for name, ptype, content in prompts:
        c.execute('INSERT OR IGNORE INTO prompt_templates (name, type, content, description) VALUES (?, ?, ?, ?)',
                  (name, ptype, content, f'Default prompt for {name}'))

    features = [
        ('pdf_upload', 1, 'Allow users to upload PDF papers'),
        ('ai_chat', 1, 'Enable AI chat with papers (RAG)'),
        ('prisma_mode', 1, 'Enable PRISMA systematic review workflow'),
        ('knowledge_graph', 1, 'Enable knowledge graph visualization'),
        ('export_pdf', 1, 'Export reviews as PDF'),
        ('export_docx', 1, 'Export reviews as DOCX'),
        ('export_bibtex', 1, 'Export citations as BibTeX'),
        ('export_ris', 1, 'Export citations as RIS'),
        ('export_excel', 1, 'Export literature matrix as Excel'),
        ('visualizations', 1, 'Enable charts and visualizations'),
    ]
    for name, enabled, desc in features:
        c.execute('INSERT OR IGNORE INTO feature_toggles (feature_name, is_enabled, description) VALUES (?, ?, ?)',
                  (name, enabled, desc))

    ai_models_defaults = [
        ('groq', 'llama-3.3-70b-versatile', 'Llama 3.3 70B Versatile (Groq)', 1),
        ('groq', 'llama-3.1-8b-instant', 'Llama 3.1 8B Instant (Groq)', 0),
        ('groq', 'llama3-8b-8192', 'Llama 3 8B (Groq)', 0),
        ('groq', 'mixtral-8x7b-32768', 'Mixtral 8x7B (Groq)', 0),
        ('groq', 'deepseek-r1-distill-llama-70b', 'DeepSeek R1 (Groq)', 0),
    ]
    for provider, model_id, display_name, is_default in ai_models_defaults:
        c.execute('INSERT OR IGNORE INTO ai_models (provider, model_id, display_name, is_default) VALUES (?, ?, ?, ?)',
                  (provider, model_id, display_name, is_default))

    api_defaults = [
        ('groq_api_key', '', 1, 'ai'),
        ('openrouter_api_key', '', 0, 'ai'),
        ('gemini_api_key', '', 0, 'ai'),
        ('ollama_url', 'http://localhost:11434', 0, 'ai'),
    ]
    for name, val, enabled, ptype in api_defaults:
        c.execute('INSERT OR IGNORE INTO api_settings (name, key_value, is_enabled, provider_type) VALUES (?, ?, ?, ?)',
                  (name, val, enabled, ptype))

    pwa_defaults = [
        ('app_name', 'Literature Review Generator'),
        ('short_name', 'LitReview'),
        ('theme_color', '#2563eb'),
        ('background_color', '#ffffff'),
        ('offline_mode', '1'),
        ('install_prompt', '1'),
    ]
    for key, val in pwa_defaults:
        c.execute('INSERT OR IGNORE INTO pwa_settings (key, value) VALUES (?, ?)', (key, val))
