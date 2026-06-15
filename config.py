import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'litreview-secret-2024-change-in-prod')
    DATABASE_PATH = os.environ.get('DATABASE_PATH', 'litreview.db')
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    ALLOWED_EXTENSIONS = {'pdf', 'txt', 'doc', 'docx'}

    GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
    OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY', '')
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
    OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://localhost:11434')

    DEFAULT_AI_PROVIDER = 'groq'
    DEFAULT_GROQ_MODEL = 'llama-3.3-70b-versatile'

    OPENALEX_BASE = 'https://api.openalex.org'
    SEMANTIC_SCHOLAR_BASE = 'https://api.semanticscholar.org/graph/v1'
    CROSSREF_BASE = 'https://api.crossref.org/works'
    PUBMED_BASE = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils'
    ARXIV_BASE = 'http://export.arxiv.org/api/query'
