import os
import re
import json
from models import get_db
from config import Config

def extract_text_from_pdf(file_path):
    text = ''
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract
        text = pdfminer_extract(file_path)
    except Exception:
        pass

    if not text or len(text.strip()) < 100:
        try:
            import PyPDF2
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text += page.extract_text() or ''
        except Exception:
            pass

    if not text or len(text.strip()) < 50:
        text = ocr_pdf(file_path)

    return text.strip()

def ocr_pdf(file_path):
    try:
        import pytesseract
        from PIL import Image
        import tempfile
        try:
            import fitz
            doc = fitz.open(file_path)
            full_text = ''
            for page in doc:
                mat = fitz.Matrix(2, 2)
                pix = page.get_pixmap(matrix=mat)
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                    pix.save(tmp.name)
                    img = Image.open(tmp.name)
                    full_text += pytesseract.image_to_string(img) + '\n'
                    os.unlink(tmp.name)
            return full_text
        except ImportError:
            pass
    except Exception:
        pass
    return ''

def detect_sections(text):
    sections = {
        'abstract': '', 'introduction': '', 'methodology': '',
        'results': '', 'discussion': '', 'conclusion': '', 'references': ''
    }
    patterns = {
        'abstract': r'(?i)\babstract\b[:\s]*(.+?)(?=\n\s*\n|\b(?:introduction|keywords)\b)',
        'introduction': r'(?i)\b(?:1\s*\.?\s*)?introduction\b[:\s]*(.+?)(?=\n\s*\n\s*\d|\b(?:2\s*\.?\s*)?(?:method|background|literature)\b)',
        'methodology': r'(?i)\b(?:\d\s*\.?\s*)?(?:method(?:ology|s)?|materials?\s+and\s+methods?)\b[:\s]*(.+?)(?=\n\s*\n\s*\d|\bresult)',
        'results': r'(?i)\b(?:\d\s*\.?\s*)?results?\b[:\s]*(.+?)(?=\n\s*\n\s*\d|\b(?:discussion|conclusion)\b)',
        'discussion': r'(?i)\b(?:\d\s*\.?\s*)?discussion\b[:\s]*(.+?)(?=\n\s*\n\s*\d|\bconclusion\b)',
        'conclusion': r'(?i)\b(?:\d\s*\.?\s*)?conclusion\b[:\s]*(.+?)(?=\n\s*\n\s*\d|\breference)',
        'references': r'(?i)\breferences?\b[:\s]*(.+?)$',
    }
    for section, pattern in patterns.items():
        match = re.search(pattern, text, re.DOTALL)
        if match:
            sections[section] = match.group(1).strip()[:2000]
    return sections

def process_upload(file_path, original_name, paper_id=None):
    db = get_db()
    try:
        text = extract_text_from_pdf(file_path)
        sections = detect_sections(text)
        ocr_used = 1 if len(text) < 100 else 0

        file_size = os.path.getsize(file_path)
        filename = os.path.basename(file_path)

        cur = db.execute('''
            INSERT INTO paper_files (paper_id, filename, original_name, file_path, file_size,
                                      extracted_text, sections, ocr_used)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (paper_id, filename, original_name, file_path, file_size,
              text[:50000], json.dumps(sections), ocr_used))

        file_id = cur.lastrowid

        upload_row = db.execute('SELECT id FROM uploads WHERE filename=?', (filename,)).fetchone()
        if upload_row:
            db.execute('UPDATE uploads SET status=? WHERE id=?', ('completed', upload_row['id']))

        db.execute('INSERT INTO notifications (type, title, message) VALUES (?, ?, ?)',
                   ('upload', 'Upload Processed', f'{original_name} has been processed successfully.'))
        db.execute('INSERT INTO activity_logs (action, details) VALUES (?, ?)',
                   ('pdf_processed', f'Processed: {original_name}'))
        db.commit()
        db.close()

        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            db2 = get_db()
            db2.execute('UPDATE paper_files SET file_path=NULL WHERE id=?', (file_id,))
            db2.commit()
            db2.close()
        except Exception:
            pass

        return {'success': True, 'file_id': file_id, 'text_length': len(text), 'sections': sections,
                'text_preview': text[:500] if text else ''}
    except Exception as e:
        db.close()
        return {'success': False, 'error': str(e)}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS
