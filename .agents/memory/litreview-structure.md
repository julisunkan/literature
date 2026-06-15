---
name: LitReview Project Structure
description: Architecture decisions and constraints for the Literature Review Generator PWA
---

# Literature Review Generator — Key Architecture Decisions

## Admin Panel
- Route: `/julisunkan` — NO authentication, NO login required
- All admin pages use `admin/base.html` (standalone, not extending main `base.html`)

## No Auth System
- Zero user registration, login, passwords, or roles
- All features publicly accessible — do not add auth

## Blueprint Layout
- `blueprints/main.py` — core pages (index, search, papers, upload, dashboard, reviews, matrix, visualizations, knowledge_graph, prisma)
- `blueprints/ai_features.py` — prefix `/ai`, all AI API endpoints
- `blueprints/export_bp.py` — prefix `/export`, file downloads
- `blueprints/admin.py` — prefix `/julisunkan`, admin panel

## Database
- SQLite at `litreview.db` (Config.DATABASE_PATH)
- All tables initialized in `models/__init__.py` via `init_db()`
- Seed defaults run on every init (INSERT OR IGNORE)

## AI Provider Hierarchy
- Primary: Groq (llama3-70b-8192)
- Fallbacks: OpenRouter → Gemini → Ollama
- API keys stored in `api_settings` table, NOT in env vars (configurable from admin)
- Groq key also falls back to `Config.GROQ_API_KEY` env var

**Why:** All configuration should be changeable from the admin panel without redeployment.

## PWA
- Manifest at `/static/manifest.json`
- Service worker at `/static/sw.js`
- Offline page at `/offline`
- SW does NOT cache `/julisunkan/*` or API routes

## Packages installed
- Flask, requests, PyPDF2, pdfminer.six, python-docx, openpyxl, markdown, bleach, numpy, groq, reportlab, python-dotenv
- faiss-cpu and sentence-transformers NOT installed (optional for RAG)
