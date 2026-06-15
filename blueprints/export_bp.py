from flask import Blueprint, request, jsonify, send_file, redirect, url_for
from models import get_db
import os

export_bp = Blueprint('export', __name__, url_prefix='/export')

@export_bp.route('/review/<int:review_id>/markdown')
def review_markdown(review_id):
    from services.export_service import export_review_markdown
    path = export_review_markdown(review_id)
    if not path:
        return 'Review not found', 404
    return send_file(path, as_attachment=True, download_name=os.path.basename(path))

@export_bp.route('/review/<int:review_id>/html')
def review_html(review_id):
    from services.export_service import export_review_html
    path = export_review_html(review_id)
    if not path:
        return 'Review not found', 404
    return send_file(path, as_attachment=True, download_name=os.path.basename(path))

@export_bp.route('/review/<int:review_id>/docx')
def review_docx(review_id):
    from services.export_service import export_review_docx
    path = export_review_docx(review_id)
    if not path:
        return 'Export failed - python-docx may not be installed', 500
    return send_file(path, as_attachment=True, download_name=os.path.basename(path))

@export_bp.route('/matrix/csv')
def matrix_csv():
    from services.export_service import export_literature_matrix_csv
    ids = request.args.getlist('ids', type=int) or None
    path = export_literature_matrix_csv(ids)
    return send_file(path, as_attachment=True, download_name=os.path.basename(path))

@export_bp.route('/matrix/excel')
def matrix_excel():
    from services.export_service import export_literature_matrix_excel
    ids = request.args.getlist('ids', type=int) or None
    path = export_literature_matrix_excel(ids)
    return send_file(path, as_attachment=True, download_name=os.path.basename(path))

@export_bp.route('/citations/bibtex')
def citations_bibtex():
    from services.export_service import export_bibtex_all
    ids = request.args.getlist('ids', type=int) or None
    path = export_bibtex_all(ids)
    return send_file(path, as_attachment=True, download_name=os.path.basename(path),
                     mimetype='application/x-bibtex')

@export_bp.route('/citations/ris')
def citations_ris():
    from services.export_service import export_ris_all
    ids = request.args.getlist('ids', type=int) or None
    path = export_ris_all(ids)
    return send_file(path, as_attachment=True, download_name=os.path.basename(path))

@export_bp.route('/api/citation/<int:paper_id>', methods=['POST'])
def generate_citation(paper_id):
    from services.citation_service import generate_citation
    data = request.get_json()
    style = data.get('style', 'apa')
    result = generate_citation(paper_id, style)
    if not result:
        return jsonify({'error': 'Paper not found'}), 404
    return jsonify({'success': True, **result})
