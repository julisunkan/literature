import re
from models import get_db

def format_authors_apa(authors_str, max_authors=7):
    if not authors_str:
        return ''
    authors = [a.strip() for a in authors_str.split(',')]
    formatted = []
    for author in authors[:max_authors]:
        parts = author.strip().split()
        if len(parts) >= 2:
            last = parts[-1]
            initials = '. '.join([p[0] for p in parts[:-1]]) + '.'
            formatted.append(f'{last}, {initials}')
        else:
            formatted.append(author)
    if len(authors) > max_authors:
        formatted.append('... ' + formatted[-1])
        formatted = formatted[:max_authors]
    if len(formatted) == 1:
        return formatted[0]
    elif len(formatted) == 2:
        return f'{formatted[0]}, & {formatted[1]}'
    else:
        return ', '.join(formatted[:-1]) + f', & {formatted[-1]}'

def generate_apa(paper):
    authors = format_authors_apa(paper.get('authors', ''))
    year = paper.get('year', 'n.d.')
    title = paper.get('title', '').strip('.')
    journal = paper.get('journal', '')
    doi = paper.get('doi', '')
    citation = f'{authors} ({year}). {title}.'
    if journal:
        citation += f' *{journal}*.'
    if doi:
        citation += f' https://doi.org/{doi}'
    in_text = _apa_intext(paper.get('authors', ''), paper.get('year', 'n.d.'))
    return citation.strip(), in_text

def _apa_intext(authors_str, year):
    if not authors_str:
        return f'(Unknown, {year})'
    authors = [a.strip() for a in authors_str.split(',')]
    if len(authors) == 1:
        last = authors[0].split()[-1] if authors[0].split() else authors[0]
        return f'({last}, {year})'
    elif len(authors) == 2:
        l1 = authors[0].split()[-1]
        l2 = authors[1].split()[-1]
        return f'({l1} & {l2}, {year})'
    else:
        last = authors[0].split()[-1] if authors[0].split() else authors[0]
        return f'({last} et al., {year})'

def generate_mla(paper):
    authors_str = paper.get('authors', '')
    authors = [a.strip() for a in authors_str.split(',')]
    if len(authors) == 1:
        parts = authors[0].split()
        if len(parts) >= 2:
            author_part = f"{parts[-1]}, {' '.join(parts[:-1])}"
        else:
            author_part = authors[0]
    elif len(authors) == 2:
        parts1 = authors[0].split()
        a1 = f"{parts1[-1]}, {' '.join(parts1[:-1])}" if len(parts1) >= 2 else authors[0]
        author_part = f'{a1}, and {authors[1]}'
    else:
        parts1 = authors[0].split()
        a1 = f"{parts1[-1]}, {' '.join(parts1[:-1])}" if len(parts1) >= 2 else authors[0]
        author_part = f'{a1}, et al.'

    title = paper.get('title', '')
    journal = paper.get('journal', '')
    year = paper.get('year', '')
    doi = paper.get('doi', '')
    citation = f'{author_part}. "{title}."'
    if journal:
        citation += f' *{journal}*,'
    if year:
        citation += f' {year}.'
    if doi:
        citation += f' doi:{doi}.'
    in_text = f'({authors[0].split()[-1] if authors else "Unknown"})'
    return citation, in_text

def generate_chicago(paper):
    authors_str = paper.get('authors', '')
    authors = [a.strip() for a in authors_str.split(',')]
    title = paper.get('title', '')
    journal = paper.get('journal', '')
    year = paper.get('year', '')
    doi = paper.get('doi', '')
    if authors:
        parts = authors[0].split()
        first_author = f"{parts[-1]}, {' '.join(parts[:-1])}" if len(parts) >= 2 else authors[0]
        rest = ', '.join(authors[1:]) if len(authors) > 1 else ''
        author_part = f'{first_author}{", " + rest if rest else ""}'
    else:
        author_part = ''
    citation = f'{author_part}. "{title}."'
    if journal:
        citation += f' *{journal}*'
    if year:
        citation += f' ({year}).'
    if doi:
        citation += f' https://doi.org/{doi}.'
    in_text = f'({authors[0].split()[-1] if authors else "Unknown"} {year})'
    return citation, in_text

def generate_harvard(paper):
    authors_str = paper.get('authors', '')
    authors = [a.strip() for a in authors_str.split(',')]
    year = paper.get('year', 'n.d.')
    title = paper.get('title', '')
    journal = paper.get('journal', '')
    doi = paper.get('doi', '')
    formatted = []
    for author in authors[:3]:
        parts = author.strip().split()
        if len(parts) >= 2:
            initials = '. '.join([p[0] for p in parts[:-1]]) + '.'
            formatted.append(f'{parts[-1]}, {initials}')
        else:
            formatted.append(author)
    if len(authors) > 3:
        author_part = ', '.join(formatted) + ' et al.'
    else:
        author_part = ', '.join(formatted)
    citation = f'{author_part} ({year}) \'{title}\'.'
    if journal:
        citation += f' *{journal}*.'
    if doi:
        citation += f' doi:{doi}.'
    in_text = f'({formatted[0].split(",")[0] if formatted else "Unknown"}, {year})'
    return citation, in_text

def generate_ieee(paper, ref_num=1):
    authors_str = paper.get('authors', '')
    authors = [a.strip() for a in authors_str.split(',')]
    formatted = []
    for author in authors[:6]:
        parts = author.strip().split()
        if len(parts) >= 2:
            initials = '. '.join([p[0] for p in parts[:-1]]) + '.'
            formatted.append(f'{initials} {parts[-1]}')
        else:
            formatted.append(author)
    if len(authors) > 6:
        formatted.append('et al.')
    author_part = ', '.join(formatted)
    title = paper.get('title', '')
    journal = paper.get('journal', '')
    year = paper.get('year', '')
    doi = paper.get('doi', '')
    citation = f'{author_part}, "{title},"'
    if journal:
        citation += f' *{journal}*,'
    if year:
        citation += f' {year}.'
    if doi:
        citation += f' doi: {doi}.'
    return citation, f'[{ref_num}]'

def generate_bibtex(paper):
    authors_str = paper.get('authors', '')
    year = paper.get('year', '')
    title = paper.get('title', '')
    journal = paper.get('journal', '')
    doi = paper.get('doi', '')
    authors = [a.strip() for a in authors_str.split(',')]
    key = ''
    if authors:
        last = authors[0].split()[-1].lower() if authors[0].split() else 'unknown'
        key = f'{last}{year}' if year else last
    key = re.sub(r'[^a-z0-9]', '', key) or 'paper'
    bibtex = f'@article{{{key},\n'
    bibtex += f'  author = {{{" and ".join(authors)}}},\n'
    bibtex += f'  title = {{{title}}},\n'
    if journal:
        bibtex += f'  journal = {{{journal}}},\n'
    if year:
        bibtex += f'  year = {{{year}}},\n'
    if doi:
        bibtex += f'  doi = {{{doi}}},\n'
    bibtex += '}'
    return bibtex

def generate_ris(paper):
    authors_str = paper.get('authors', '')
    authors = [a.strip() for a in authors_str.split(',')]
    ris = 'TY  - JOUR\n'
    for author in authors:
        ris += f'AU  - {author}\n'
    ris += f'TI  - {paper.get("title", "")}\n'
    if paper.get('journal'):
        ris += f'JO  - {paper.get("journal")}\n'
    if paper.get('year'):
        ris += f'PY  - {paper.get("year")}\n'
    if paper.get('doi'):
        ris += f'DO  - {paper.get("doi")}\n'
    if paper.get('abstract'):
        ris += f'AB  - {paper.get("abstract","")[:500]}\n'
    ris += 'ER  -\n'
    return ris

def generate_citation(paper_id, style='apa'):
    db = get_db()
    paper = db.execute('SELECT * FROM papers WHERE id=?', (paper_id,)).fetchone()
    db.close()
    if not paper:
        return None
    paper = dict(paper)
    style = style.lower()
    if style == 'apa':
        citation, in_text = generate_apa(paper)
    elif style == 'mla':
        citation, in_text = generate_mla(paper)
    elif style == 'chicago':
        citation, in_text = generate_chicago(paper)
    elif style == 'harvard':
        citation, in_text = generate_harvard(paper)
    elif style == 'ieee':
        citation, in_text = generate_ieee(paper)
    else:
        citation, in_text = generate_apa(paper)

    bibtex = generate_bibtex(paper)
    ris = generate_ris(paper)

    db = get_db()
    existing = db.execute('SELECT id FROM citations WHERE paper_id=? AND style=?', (paper_id, style)).fetchone()
    if existing:
        db.execute('UPDATE citations SET citation_text=?, in_text=?, bibtex=?, ris=? WHERE id=?',
                   (citation, in_text, bibtex, ris, existing['id']))
    else:
        db.execute('INSERT INTO citations (paper_id, style, citation_text, in_text, bibtex, ris) VALUES (?, ?, ?, ?, ?, ?)',
                   (paper_id, style, citation, in_text, bibtex, ris))
    db.commit()
    db.close()
    return {'citation': citation, 'in_text': in_text, 'bibtex': bibtex, 'ris': ris}
