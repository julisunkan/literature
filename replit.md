# Literature Review Generator

A free, AI-powered Progressive Web App (PWA) for academic research. Generate literature reviews, analyze papers, detect research gaps, and manage research workflows.

## Stack
- **Backend**: Python Flask with SQLite
- **AI**: Groq (primary), OpenRouter, Gemini, Ollama (fallbacks)
- **Academic APIs**: OpenAlex, Semantic Scholar, Crossref, PubMed, arXiv
- **Frontend**: Bootstrap 5, Chart.js, D3.js
- **PWA**: Service Worker + manifest for offline support

## Run
```
python main.py
```

## Admin Panel
Access at `/julisunkan` — no login required.

## Setup Groq API
1. Go to `/julisunkan/api-management`
2. Add your Groq API key (get one free at console.groq.com)

## User Preferences
- No authentication system
- Public access to all features
- Admin at /julisunkan (no password)
- Bootstrap 5 responsive UI
- Academic clean design
