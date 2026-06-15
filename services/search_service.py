import requests
import xml.etree.ElementTree as ET
from models import get_db
import json

HEADERS = {'User-Agent': 'LitReview/1.0 (mailto:admin@litreview.app)'}

def search_openalex(query, year_from=None, year_to=None, limit=20):
    params = {
        'search': query,
        'per-page': limit,
        'select': 'id,title,authorships,publication_year,doi,primary_location,abstract_inverted_index,cited_by_count,keywords'
    }
    if year_from or year_to:
        filters = []
        if year_from:
            filters.append(f'from_publication_date:{year_from}-01-01')
        if year_to:
            filters.append(f'to_publication_date:{year_to}-12-31')
        params['filter'] = ','.join(filters)

    try:
        resp = requests.get('https://api.openalex.org/works', params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        results = []
        for item in data.get('results', []):
            abstract = ''
            if item.get('abstract_inverted_index'):
                idx = item['abstract_inverted_index']
                words = {}
                for word, positions in idx.items():
                    for pos in positions:
                        words[pos] = word
                abstract = ' '.join(words[k] for k in sorted(words.keys()))

            authors = ', '.join([
                a['author']['display_name']
                for a in item.get('authorships', [])[:5]
                if a.get('author')
            ])
            journal = ''
            if item.get('primary_location') and item['primary_location'].get('source'):
                journal = item['primary_location']['source'].get('display_name', '')

            results.append({
                'title': item.get('title', ''),
                'authors': authors,
                'year': item.get('publication_year'),
                'doi': item.get('doi', '').replace('https://doi.org/', '') if item.get('doi') else '',
                'abstract': abstract,
                'journal': journal,
                'citations_count': item.get('cited_by_count', 0),
                'source': 'OpenAlex',
                'url': item.get('id', ''),
                'keywords': ', '.join([k['display_name'] for k in item.get('keywords', [])])
            })
        return results
    except Exception as e:
        log_search_error('openalex', str(e))
        return []

def search_semantic_scholar(query, year_from=None, year_to=None, limit=20):
    params = {
        'query': query,
        'limit': limit,
        'fields': 'title,authors,year,externalIds,abstract,venue,citationCount,tldr'
    }
    try:
        resp = requests.get('https://api.semanticscholar.org/graph/v1/paper/search',
                            params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        results = []
        for item in data.get('data', []):
            year = item.get('year')
            if year_from and year and year < year_from:
                continue
            if year_to and year and year > year_to:
                continue
            authors = ', '.join([a['name'] for a in item.get('authors', [])[:5]])
            doi = ''
            if item.get('externalIds'):
                doi = item['externalIds'].get('DOI', '')
            abstract = item.get('abstract', '')
            if not abstract and item.get('tldr'):
                abstract = item['tldr'].get('text', '')
            results.append({
                'title': item.get('title', ''),
                'authors': authors,
                'year': year,
                'doi': doi,
                'abstract': abstract,
                'journal': item.get('venue', ''),
                'citations_count': item.get('citationCount', 0),
                'source': 'Semantic Scholar',
                'url': f"https://www.semanticscholar.org/paper/{item.get('paperId','')}",
                'keywords': ''
            })
        return results
    except Exception as e:
        log_search_error('semantic_scholar', str(e))
        return []

def search_crossref(query, year_from=None, year_to=None, limit=20):
    params = {
        'query': query,
        'rows': limit,
        'select': 'title,author,published,DOI,abstract,container-title,is-referenced-by-count,subject'
    }
    if year_from:
        params['filter'] = f'from-pub-date:{year_from}'
    try:
        resp = requests.get('https://api.crossref.org/works', params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        results = []
        for item in data.get('message', {}).get('items', []):
            year = None
            if item.get('published'):
                dp = item['published'].get('date-parts', [[]])
                if dp and dp[0]:
                    year = dp[0][0]
            if year_to and year and year > year_to:
                continue
            authors = ', '.join([
                f"{a.get('given','')} {a.get('family','')}".strip()
                for a in item.get('author', [])[:5]
            ])
            title = item.get('title', [''])[0] if item.get('title') else ''
            journal = item.get('container-title', [''])[0] if item.get('container-title') else ''
            abstract = item.get('abstract', '')
            if abstract:
                import re
                abstract = re.sub('<[^<]+?>', '', abstract)
            results.append({
                'title': title,
                'authors': authors,
                'year': year,
                'doi': item.get('DOI', ''),
                'abstract': abstract,
                'journal': journal,
                'citations_count': item.get('is-referenced-by-count', 0),
                'source': 'Crossref',
                'url': f"https://doi.org/{item.get('DOI','')}",
                'keywords': ', '.join(item.get('subject', []))
            })
        return results
    except Exception as e:
        log_search_error('crossref', str(e))
        return []

def search_pubmed(query, year_from=None, year_to=None, limit=20):
    try:
        search_params = {
            'db': 'pubmed', 'term': query, 'retmax': limit,
            'retmode': 'json', 'sort': 'relevance'
        }
        if year_from:
            search_params['mindate'] = str(year_from)
        if year_to:
            search_params['maxdate'] = str(year_to)
        resp = requests.get('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi',
                            params=search_params, timeout=15)
        resp.raise_for_status()
        ids = resp.json().get('esearchresult', {}).get('idlist', [])
        if not ids:
            return []
        fetch_params = {
            'db': 'pubmed', 'id': ','.join(ids),
            'retmode': 'xml', 'rettype': 'abstract'
        }
        fetch_resp = requests.get('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi',
                                   params=fetch_params, timeout=15)
        fetch_resp.raise_for_status()
        root = ET.fromstring(fetch_resp.content)
        results = []
        for article in root.findall('.//PubmedArticle'):
            try:
                title_el = article.find('.//ArticleTitle')
                title = title_el.text if title_el is not None else ''
                abstract_texts = article.findall('.//AbstractText')
                abstract = ' '.join([t.text or '' for t in abstract_texts])
                authors = []
                for author in article.findall('.//Author')[:5]:
                    last = author.find('LastName')
                    first = author.find('ForeName')
                    if last is not None:
                        name = last.text or ''
                        if first is not None:
                            name = f"{first.text} {name}"
                        authors.append(name)
                year_el = article.find('.//PubDate/Year')
                year = int(year_el.text) if year_el is not None and year_el.text else None
                pmid_el = article.find('.//PMID')
                pmid = pmid_el.text if pmid_el is not None else ''
                journal_el = article.find('.//Journal/Title')
                journal = journal_el.text if journal_el is not None else ''
                doi_el = article.find('.//ArticleId[@IdType="doi"]')
                doi = doi_el.text if doi_el is not None else ''
                results.append({
                    'title': title, 'authors': ', '.join(authors),
                    'year': year, 'doi': doi, 'abstract': abstract,
                    'journal': journal, 'citations_count': 0,
                    'source': 'PubMed',
                    'url': f'https://pubmed.ncbi.nlm.nih.gov/{pmid}/',
                    'keywords': ''
                })
            except Exception:
                continue
        return results
    except Exception as e:
        log_search_error('pubmed', str(e))
        return []

def search_arxiv(query, year_from=None, year_to=None, limit=20):
    params = {
        'search_query': f'all:{query}',
        'start': 0, 'max_results': limit,
        'sortBy': 'relevance', 'sortOrder': 'descending'
    }
    try:
        resp = requests.get('http://export.arxiv.org/api/query', params=params, timeout=15)
        resp.raise_for_status()
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        root = ET.fromstring(resp.content)
        results = []
        for entry in root.findall('atom:entry', ns):
            try:
                title = entry.find('atom:title', ns).text.strip().replace('\n', ' ')
                abstract = entry.find('atom:summary', ns).text.strip()
                published = entry.find('atom:published', ns).text
                year = int(published[:4]) if published else None
                if year_from and year and year < year_from:
                    continue
                if year_to and year and year > year_to:
                    continue
                authors = ', '.join([
                    a.find('atom:name', ns).text
                    for a in entry.findall('atom:author', ns)[:5]
                    if a.find('atom:name', ns) is not None
                ])
                arxiv_id = entry.find('atom:id', ns).text
                doi_el = entry.find('{http://arxiv.org/schemas/atom}doi')
                doi = doi_el.text if doi_el is not None else ''
                categories = [c.get('term') for c in entry.findall('{http://www.w3.org/2005/Atom}category')]
                results.append({
                    'title': title, 'authors': authors, 'year': year,
                    'doi': doi, 'abstract': abstract, 'journal': 'arXiv',
                    'citations_count': 0, 'source': 'arXiv',
                    'url': arxiv_id,
                    'keywords': ', '.join(categories[:5])
                })
            except Exception:
                continue
        return results
    except Exception as e:
        log_search_error('arxiv', str(e))
        return []

def search_all(query, sources=None, year_from=None, year_to=None, limit=10):
    if sources is None:
        sources = ['openalex', 'semantic_scholar', 'crossref', 'pubmed', 'arxiv']
    all_results = []
    if 'openalex' in sources:
        all_results.extend(search_openalex(query, year_from, year_to, limit))
    if 'semantic_scholar' in sources:
        all_results.extend(search_semantic_scholar(query, year_from, year_to, limit))
    if 'crossref' in sources:
        all_results.extend(search_crossref(query, year_from, year_to, limit))
    if 'pubmed' in sources:
        all_results.extend(search_pubmed(query, year_from, year_to, limit))
    if 'arxiv' in sources:
        all_results.extend(search_arxiv(query, year_from, year_to, limit))
    return all_results

def save_paper(paper_data):
    db = get_db()
    existing = db.execute('SELECT id FROM papers WHERE doi=? AND doi != ""', (paper_data.get('doi', ''),)).fetchone()
    if existing:
        db.close()
        return existing['id']
    cur = db.execute('''
        INSERT INTO papers (title, authors, abstract, year, doi, url, journal, citations_count, source, keywords)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        paper_data.get('title', ''), paper_data.get('authors', ''),
        paper_data.get('abstract', ''), paper_data.get('year'),
        paper_data.get('doi', ''), paper_data.get('url', ''),
        paper_data.get('journal', ''), paper_data.get('citations_count', 0),
        paper_data.get('source', ''), paper_data.get('keywords', '')
    ))
    paper_id = cur.lastrowid
    db.execute('INSERT INTO activity_logs (action, details) VALUES (?, ?)',
               ('paper_saved', f"Saved paper: {paper_data.get('title', '')[:100]}"))
    db.commit()
    db.close()
    return paper_id

def log_search_error(source, error):
    try:
        db = get_db()
        db.execute('INSERT INTO system_logs (level, source, message) VALUES (?, ?, ?)',
                   ('ERROR', f'search:{source}', error[:500]))
        db.commit()
        db.close()
    except Exception:
        pass
