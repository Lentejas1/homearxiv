import json
import os
import re
import sqlite3
import threading
import time
import webbrowser
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import URLError

from flask import Flask, jsonify, render_template, request

PDF_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "papers")
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "papers.db")

app = Flask(__name__)

ARXIV_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}

ARXIV_CATEGORIES = {
    "math.AC": "Commutative Algebra", "math.AG": "Algebraic Geometry", "math.AP": "Analysis of PDEs",
    "math.AT": "Algebraic Topology", "math.CA": "Classical Analysis and ODEs", "math.CO": "Combinatorics",
    "math.CT": "Category Theory", "math.CV": "Complex Variables", "math.DG": "Differential Geometry",
    "math.DS": "Dynamical Systems", "math.FA": "Functional Analysis", "math.GM": "General Mathematics",
    "math.GN": "General Topology", "math.GR": "Group Theory", "math.GT": "Geometric Topology",
    "math.HO": "History and Overview", "math.IT": "Information Theory", "math.KT": "K-Theory and Homology",
    "math.LO": "Logic", "math.MG": "Metric Geometry", "math.MP": "Mathematical Physics",
    "math.NA": "Numerical Analysis", "math.NT": "Number Theory", "math.OA": "Operator Algebras",
    "math.OC": "Optimization and Control", "math.PR": "Probability", "math.QA": "Quantum Algebra",
    "math.RA": "Rings and Algebras", "math.RT": "Representation Theory", "math.SG": "Symplectic Geometry",
    "math.SP": "Spectral Theory", "math.ST": "Statistics Theory",
    "cs.AI": "Artificial Intelligence", "cs.AR": "Hardware Architecture", "cs.CC": "Computational Complexity",
    "cs.CE": "Computational Engineering", "cs.CG": "Computational Geometry", "cs.CL": "Computation and Language",
    "cs.CR": "Cryptography and Security", "cs.CV": "Computer Vision", "cs.CY": "Computers and Society",
    "cs.DB": "Databases", "cs.DC": "Distributed Computing", "cs.DL": "Digital Libraries",
    "cs.DS": "Data Structures and Algorithms", "cs.ET": "Emerging Technologies",
    "cs.FL": "Formal Languages and Automata Theory", "cs.GL": "General Literature", "cs.GR": "Graphics",
    "cs.GT": "Computer Science and Game Theory", "cs.HC": "Human-Computer Interaction",
    "cs.IR": "Information Retrieval", "cs.IT": "Information Theory", "cs.LG": "Machine Learning",
    "cs.LO": "Logic in Computer Science", "cs.MA": "Multiagent Systems", "cs.MM": "Multimedia",
    "cs.MS": "Mathematical Software", "cs.NA": "Numerical Analysis", "cs.NE": "Neural and Evolutionary Computing",
    "cs.NI": "Networking and Internet Architecture", "cs.OS": "Operating Systems", "cs.PF": "Performance",
    "cs.PL": "Programming Languages", "cs.RO": "Robotics", "cs.SC": "Symbolic Computation",
    "cs.SD": "Sound", "cs.SE": "Software Engineering", "cs.SI": "Social and Information Networks",
    "cs.SY": "Systems and Control",
    "physics.acc-ph": "Accelerator Physics", "physics.ao-ph": "Atmospheric and Oceanic Physics",
    "physics.app-ph": "Applied Physics", "physics.atm-clus": "Atomic and Molecular Clusters",
    "physics.atom-ph": "Atomic Physics", "physics.bio-ph": "Biological Physics",
    "physics.chem-ph": "Chemical Physics", "physics.class-ph": "Classical Physics",
    "physics.comp-ph": "Computational Physics", "physics.data-an": "Data Analysis and Statistics",
    "physics.flu-dyn": "Fluid Dynamics", "physics.gen-ph": "General Physics", "physics.geo-ph": "Geophysics",
    "physics.hist-ph": "History and Philosophy of Physics", "physics.ins-det": "Instrumentation and Detectors",
    "physics.med-ph": "Medical Physics", "physics.optics": "Optics", "physics.plasm-ph": "Plasma Physics",
    "physics.pop-ph": "Popular Physics", "physics.soc-ph": "Physics and Society",
    "physics.space-ph": "Space Physics",
    "astro-ph.CO": "Cosmology and Nongalactic Astrophysics", "astro-ph.EP": "Earth and Planetary Astrophysics",
    "astro-ph.GA": "Astrophysics of Galaxies", "astro-ph.HE": "High Energy Astrophysics",
    "astro-ph.IM": "Instrumentation and Methods for Astrophysics", "astro-ph.SR": "Solar and Stellar Astrophysics",
    "cond-mat.dis-nn": "Disordered Systems and Neural Networks",
    "cond-mat.mes-hall": "Mesoscale and Nanoscale Physics", "cond-mat.mtrl-sci": "Materials Science",
    "cond-mat.other": "Other Condensed Matter", "cond-mat.quant-gas": "Quantum Gases",
    "cond-mat.soft": "Soft Condensed Matter", "cond-mat.stat-mech": "Statistical Mechanics",
    "cond-mat.str-el": "Strongly Correlated Electrons", "cond-mat.supr-con": "Superconductivity",
    "gr-qc": "General Relativity and Quantum Cosmology", "hep-ex": "High Energy Physics - Experiment",
    "hep-lat": "High Energy Physics - Lattice", "hep-ph": "High Energy Physics - Phenomenology",
    "hep-th": "High Energy Physics - Theory", "math-ph": "Mathematical Physics",
    "nlin.AO": "Adaptation and Self-Organizing Systems", "nlin.CD": "Chaotic Dynamics",
    "nlin.CG": "Cellular Automata and Lattice Gases", "nlin.PS": "Pattern Formation and Solitons",
    "nlin.SI": "Exactly Solvable and Integrable Systems", "nucl-ex": "Nuclear Experiment",
    "nucl-th": "Nuclear Theory",
    "q-bio.BM": "Biomolecules", "q-bio.CB": "Cell Behavior", "q-bio.GN": "Genomics",
    "q-bio.MN": "Molecular Networks", "q-bio.NC": "Neurons and Cognition", "q-bio.OT": "Other Quantitative Biology",
    "q-bio.PE": "Populations and Evolution", "q-bio.QM": "Quantitative Methods",
    "q-bio.SC": "Subcellular Processes", "q-bio.TO": "Tissues and Organs",
    "q-fin.CP": "Computational Finance", "q-fin.EC": "Economics", "q-fin.GN": "General Finance",
    "q-fin.MF": "Mathematical Finance", "q-fin.PM": "Portfolio Management",
    "q-fin.PR": "Pricing of Securities", "q-fin.RM": "Risk Management", "q-fin.ST": "Statistical Finance",
    "q-fin.TR": "Trading and Market Microstructure",
    "stat.AP": "Statistics - Applications", "stat.CO": "Statistics - Computation",
    "stat.ME": "Statistics - Methodology", "stat.ML": "Statistics - Machine Learning",
    "stat.OT": "Statistics - Other", "stat.TH": "Statistics - Theory",
    "eess.AS": "Audio and Speech Processing", "eess.IV": "Image and Video Processing",
    "eess.SP": "Signal Processing", "eess.SY": "Systems and Control",
}

# ── Global resolve progress ──────────────────────────────────────────────────

resolve_state = {"running": False, "total": 0, "current": 0, "current_id": None, "current_label": ""}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            title TEXT,
            author TEXT,
            year INTEGER,
            doi TEXT,
            abstract TEXT,
            path TEXT NOT NULL UNIQUE,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );
        CREATE TABLE IF NOT EXISTS document_tags (
            document_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            PRIMARY KEY (document_id, tag_id),
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
        );
    """)
    for col in ("doi", "abstract", "doc_type"):
        try:
            conn.execute(f"ALTER TABLE documents ADD COLUMN {col} TEXT DEFAULT 'paper'")
        except sqlite3.OperationalError:
            pass
    try:
        conn.execute("ALTER TABLE documents ADD COLUMN category TEXT")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()


# ── Helpers ──────────────────────────────────────────────────────────────────

DUP_SUFFIX = re.compile(r"\s*[-–—]?\s*(?:copy|copia|duplicate|dup|\((\d+)\)|\[(\d+)\])$", re.IGNORECASE)

def normalize_filename(name):
    name = os.path.splitext(name)[0]
    name = DUP_SUFFIX.sub("", name.strip()).strip()
    name = re.sub(r"\s+", " ", name).strip()
    return name.lower()


def find_duplicates():
    conn = get_db()
    rows = conn.execute("SELECT id, filename, title, author FROM documents").fetchall()
    groups = {}
    for r in rows:
        groups.setdefault(normalize_filename(r["filename"]), []).append(dict(r))
    to_delete = []
    for key, docs in groups.items():
        if len(docs) < 2:
            continue
        docs.sort(key=lambda d: (2 if d["title"] and d["title"] != d["filename"].replace(".pdf", "") else 0) + (1 if d["author"] else 0), reverse=True)
        to_delete.extend(d["id"] for d in docs[1:])
    conn.close()
    return to_delete


def dedup():
    to_delete = find_duplicates()
    if not to_delete:
        return 0
    conn = get_db()
    placeholders = ",".join("?" for _ in to_delete)
    conn.execute(f"DELETE FROM documents WHERE id IN ({placeholders})", to_delete)
    conn.execute("DELETE FROM tags WHERE id NOT IN (SELECT DISTINCT tag_id FROM document_tags)")
    conn.commit()
    count = len(to_delete)
    conn.execute("DELETE FROM tags WHERE id NOT IN (SELECT DISTINCT tag_id FROM document_tags)")
    conn.commit()
    conn.close()
    return count


def clean_title(text):
    if not text:
        return text
    return re.sub(r"\.pdf$", "", text.strip(), flags=re.IGNORECASE).strip()


DOI_PATTERN = re.compile(r"^10\.\d{4,}/.+$")
ISBN_CLEAN = re.compile(r"^(?:978|979)?\d{9}[\dXx]$")
ARXIV_CLEAN = re.compile(r"^arxiv:|\.pdf$|v\d+$", re.IGNORECASE)

def is_doi(text):
    return bool(text and DOI_PATTERN.match(text.strip()))

def is_isbn(text):
    if not text:
        return False
    return bool(ISBN_CLEAN.match(text.strip().replace("-", "").replace(" ", "")))

def is_arxiv_id(text):
    if not text or is_isbn(text):
        return False
    t = re.sub(ARXIV_CLEAN, "", text.strip()).strip()
    t = t.replace(".", "").replace("/", "").replace("-", "").replace(" ", "")
    return bool(re.match(r"^\d{8,}$", t))

def normalize_arxiv_id(text):
    t = re.sub(ARXIV_CLEAN, "", text.strip()).strip()
    t = t.replace(" ", "").replace("/", "").replace("-", "").replace(".pdf", "")
    t = re.sub(r"v\d+$", "", t, flags=re.IGNORECASE)
    if re.match(r"^\d{8,}$", t):
        return f"{t[:4]}.{t[4:]}"
    return t


# ── Resolvers ────────────────────────────────────────────────────────────────

def resolve_doi(doi):
    req = Request(f"https://api.crossref.org/works/{doi.strip()}", headers={"User-Agent": "HomeArxiv/1.0 (mailto:user@example.com)"})
    try:
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        try:
            time.sleep(1)
            with urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
        except Exception:
            return None
    msg = data.get("message", {})
    title = (msg.get("title") or [None])[0]
    authors = msg.get("author", [])
    author = ", ".join(f"{a.get('given','')} {a.get('family','')}".strip() for a in authors if a.get("family")) or None
    dp = (msg.get("published-print",{}).get("date-parts") or msg.get("published-online",{}).get("date-parts") or msg.get("created",{}).get("date-parts") or [])
    year = dp[0][0] if dp and dp[0] else None
    abstract = msg.get("abstract", "").strip() or None
    return {"title": title, "author": author, "year": year, "doi": doi.strip(), "source": "doi", "abstract": abstract}


def resolve_arxiv(arxivid):
    arxivid = normalize_arxiv_id(arxivid)
    req = Request(f"https://export.arxiv.org/api/query?id_list={arxivid}", headers={"User-Agent": "HomeArxiv/1.0"})
    try:
        with urlopen(req, timeout=20) as resp:
            xml_data = resp.read().decode()
    except Exception:
        return None
    try:
        root = ET.fromstring(xml_data)
        entry = root.find("atom:entry", ARXIV_NS)
        if entry is None:
            return None
        title_el = entry.find("atom:title", ARXIV_NS)
        title = title_el.text.strip().replace("\n", " ").strip() if title_el is not None else None
        authors = []
        for au in entry.findall("atom:author", ARXIV_NS):
            ne = au.find("atom:name", ARXIV_NS)
            if ne is not None:
                authors.append(ne.text.strip())
        author = ", ".join(authors) if authors else None
        pub = entry.find("atom:published", ARXIV_NS)
        year = int(re.search(r"(\d{4})", pub.text).group(1)) if pub is not None else None
        summary = entry.find("atom:summary", ARXIV_NS)
        abstract = summary.text.strip().replace("\n", " ").strip() if summary is not None else None
        primary_cat_el = entry.find("arxiv:primary_category", ARXIV_NS)
        primary_cat = primary_cat_el.get("term") if primary_cat_el is not None else None
        return {"title": title, "author": author, "year": year, "doi": arxivid, "source": "arxiv", "abstract": abstract, "category": primary_cat}
    except Exception:
        return None


def resolve_isbn(isbn):
    clean = isbn.strip().replace("-", "").replace(" ", "")
    url = f"https://openlibrary.org/isbn/{clean}.json"
    req = Request(url, headers={"User-Agent": "HomeArxiv/1.0"})
    try:
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return None
    title = data.get("title") or None
    authors = data.get("authors", [])
    author = None
    if authors:
        parts = []
        for a in authors[:3]:
            key = a.get("key", "")
            if key:
                try:
                    with urlopen(f"https://openlibrary.org{key}.json", timeout=10) as aur:
                        parts.append(json.loads(aur.read().decode()).get("name", ""))
                except Exception:
                    parts.append(key.split("/")[-1].replace("_", " "))
        author = ", ".join(p for p in parts if p) or None
    year = None
    m = re.search(r"(\d{4})", data.get("publish_date", ""))
    if m:
        year = int(m.group(1))
    return {"title": title, "author": author, "year": year, "doi": clean, "source": "isbn", "abstract": None}


def resolve_any(identifier):
    cleaned = clean_title(identifier)
    if is_doi(cleaned):
        return resolve_doi(cleaned)
    if is_isbn(cleaned):
        return resolve_isbn(cleaned)
    result = resolve_arxiv(cleaned)
    if result:
        return result
    if is_arxiv_id(cleaned):
        return resolve_arxiv(normalize_arxiv_id(cleaned))
    return None


# ── Abstract & keywords extraction from PDF ──────────────────────────────────

def extract_pdf_text(path):
    try:
        import fitz
        doc = fitz.open(path)
        text = ""
        for page in doc:
            text += page.get_text()
            if len(text) > 8000:
                break
        doc.close()
        return text
    except Exception:
        return None


def parse_abstract(text):
    if not text:
        return None, []
    m = re.search(r"(?i)\babstract\b[:\s]*([\s\S]{10,}?)(?=\b(?:keywords|index terms|introduction|1\.\s|ccs\sconcepts|ams\sclassification)\b)", text)
    abstract = None
    if m:
        abstract = re.sub(r"\s+", " ", m.group(1)).strip()
        abstract = abstract[:2000] if abstract else None
    keywords = _extract_keywords(text)
    return abstract, keywords


_STOPWORDS = set("the a an is in on at of to for with by and or not be are was were has have had its their this that from as it he she they we you".split())

def _extract_keywords(text):
    if not text:
        return []
    patterns = [
        r"(?i)(?:keywords|index terms|subject classifications?)\b[:\s]*([\s\S]{3,}?)(?=\n\s*\n|\Z)",
        r"(?i)(?:keywords|index terms|subject classifications?)\b[:\s]*([^\n]{3,})",
    ]
    raw = None
    for p in patterns:
        km = re.search(p, text)
        if km:
            raw = km.group(1).strip()
            break
    if not raw:
        return []
    raw = re.sub(r"\s*\n\s*", ", ", raw)
    candidates = re.split(r"[,;]\s*", raw) if re.search(r"[,;]", raw) else re.split(r"\s{2,}|•|\*|\d+\.\s", raw)
    keywords = []
    for c in candidates:
        c = c.strip(" \t.,;:-()\"'[]").strip().lower()
        if len(c) > 2 and c not in _STOPWORDS and len(c) < 80:
            keywords.append(c)
    return keywords[:20]


# ── Scan ─────────────────────────────────────────────────────────────────────

def scan_papers():
    conn = get_db()
    existing = {row["path"] for row in conn.execute("SELECT path FROM documents").fetchall()}
    new_count = 0
    if os.path.isdir(PDF_DIR):
        for fname in os.listdir(PDF_DIR):
            if not fname.lower().endswith(".pdf"):
                continue
            fpath = os.path.join(PDF_DIR, fname)
            if fpath in existing:
                continue
            title, author, year = extract_pdf_metadata(fpath)
            doi = None
            base = os.path.splitext(fname)[0]
            if not title:
                title = clean_title(base)
            identifier = clean_title(title) if (is_doi(title) or is_arxiv_id(title) or is_isbn(title)) else clean_title(base)
            if is_doi(identifier) or is_arxiv_id(identifier) or is_isbn(identifier):
                doi = identifier
            pdf_text = extract_pdf_text(fpath)
            abstract, keywords = parse_abstract(pdf_text)
            doc_type = detect_doc_type(doi, title, fname)
            conn.execute(
                "INSERT INTO documents (filename, title, author, year, doi, abstract, path, doc_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (fname, title, author, year, doi, abstract, fpath, doc_type),
            )
            doc_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            for kw in keywords:
                conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (kw,))
                tag = conn.execute("SELECT id FROM tags WHERE name = ?", (kw,)).fetchone()
                if tag:
                    conn.execute("INSERT OR IGNORE INTO document_tags (document_id, tag_id) VALUES (?, ?)", (doc_id, tag[0]))
            new_count += 1
    conn.commit()
    conn.close()
    return new_count


def extract_pdf_metadata(path):
    try:
        import fitz
        doc = fitz.open(path)
        meta = doc.metadata
        title = meta.get("title", "").strip()
        author = meta.get("author", "").strip()
        year_str = ""
        if meta.get("creationDate"):
            m = re.search(r"D:(\d{4})", meta["creationDate"])
            if m:
                year_str = m.group(1)
        doc.close()
        return title or None, author or None, int(year_str) if year_str else None
    except ImportError:
        return None, None, None
    except Exception:
        return None, None, None


# ── Doc type & tag helpers ────────────────────────────────────────────────────

def detect_doc_type(doi, title, filename):
    if doi and is_isbn(doi):
        return "book"
    if (doi and is_arxiv_id(doi)) or (title and is_arxiv_id(title)):
        return "paper"
    return "paper"


# ── Batch resolve ────────────────────────────────────────────────────────────

def resolve_existing_unresolved():
    global resolve_state
    try:
        conn = get_db()
        rows = conn.execute(
            "SELECT id, title, filename FROM documents WHERE author IS NULL OR title = filename"
        ).fetchall()
        candidates = [r for r in rows if len(clean_title(r["title"] or r["filename"].replace(".pdf", ""))) >= 6]
        if not candidates:
            conn.close()
            return 0
        resolve_state["running"] = True
        resolve_state["total"] = len(candidates)
        resolve_state["current"] = 0
        updated = 0
        print(f"Resolviendo {len(candidates)} documento(s) en segundo plano...", flush=True)
        for idx, r in enumerate(candidates, 1):
            identifier = clean_title(r["title"] or r["filename"].replace(".pdf", ""))
            resolve_state["current"] = idx
            resolve_state["current_id"] = r["id"]
            resolve_state["current_label"] = identifier
            if not is_doi(identifier) and not is_arxiv_id(identifier) and not is_isbn(identifier):
                continue
            print(f"  [{idx}/{len(candidates)}] Resolviendo '{identifier}'...", flush=True)
            result = resolve_any(identifier)
            if result and result.get("title"):
                conn.execute(
                    "UPDATE documents SET title=?, author=?, year=?, doi=?, abstract=?, category=?, updated_at=? WHERE id=?",
                    (result["title"], result["author"], result["year"], result["doi"],
                     result.get("abstract"), result.get("category"), datetime.now().isoformat(), r["id"]),
                )
                if result.get("abstract"):
                    _, keywords = parse_abstract(result["abstract"])
                    for kw in keywords:
                        conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (kw,))
                        tag = conn.execute("SELECT id FROM tags WHERE name = ?", (kw,)).fetchone()
                        if tag:
                            conn.execute("INSERT OR IGNORE INTO document_tags (document_id, tag_id) VALUES (?, ?)", (r["id"], tag[0]))
                cat = result.get("category")
                if cat:
                    cat_name = ARXIV_CATEGORIES.get(cat, cat)
                    conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (cat_name,))
                    ct = conn.execute("SELECT id FROM tags WHERE name = ?", (cat_name,)).fetchone()
                    if ct:
                        conn.execute("INSERT OR IGNORE INTO document_tags (document_id, tag_id) VALUES (?, ?)", (r["id"], ct[0]))
                doc_type = detect_doc_type(result.get("doi"), result.get("title"), "")
                conn.execute("UPDATE documents SET doc_type=? WHERE id=?", (doc_type, r["id"]))
                conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (doc_type,))
                tt = conn.execute("SELECT id FROM tags WHERE name = ?", (doc_type,)).fetchone()
                if tt:
                    conn.execute("INSERT OR IGNORE INTO document_tags (document_id, tag_id) VALUES (?, ?)", (r["id"], tt[0]))
                updated += 1
                print(f"    -> {result['title'][:60]}", flush=True)
            time.sleep(0.15)
        if updated:
            conn.commit()
        conn.close()
        resolve_state["running"] = False
        print(f"Resueltos {updated} documento(s)", flush=True)
        return updated
    except Exception as e:
        print(f"ERROR en resolve_existing_unresolved: {e}", flush=True)
        import traceback
        traceback.print_exc()
        resolve_state["running"] = False
        return 0


# ── API Routes ───────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/documents")
def get_documents():
    conn = get_db()
    search = request.args.get("search", "").strip()
    tag_filter = request.args.get("tag", "").strip()
    type_filter = request.args.get("type", "").strip()
    query = """
        SELECT d.*, GROUP_CONCAT(t.name, ', ') AS tags
        FROM documents d
        LEFT JOIN document_tags dt ON d.id = dt.document_id
        LEFT JOIN tags t ON dt.tag_id = t.id
    """
    params = []
    conditions = []
    if search:
        conditions.append("(d.title LIKE ? OR d.author LIKE ? OR d.filename LIKE ? OR d.doi LIKE ? OR d.abstract LIKE ?)")
        params.extend([f"%{search}%"] * 5)
    if tag_filter:
        conditions.append("d.id IN (SELECT dt2.document_id FROM document_tags dt2 JOIN tags t2 ON dt2.tag_id = t2.id WHERE t2.name = ?)")
        params.append(tag_filter)
    if type_filter:
        conditions.append("d.doc_type = ?")
        params.append(type_filter)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " GROUP BY d.id ORDER BY d.updated_at DESC"
    docs = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify([dict(row) for row in docs])


@app.route("/api/documents/<int:doc_id>", methods=["PUT"])
def update_document(doc_id):
    data = request.get_json()
    conn = get_db()
    fields = []
    params = []
    for key in ("title", "author", "year", "doi", "doc_type"):
        if key in data:
            fields.append(f"{key} = ?")
            params.append(data[key])
    if fields:
        fields.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        params.append(doc_id)
        conn.execute(f"UPDATE documents SET {', '.join(fields)} WHERE id = ?", params)
        conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/documents/<int:doc_id>", methods=["DELETE"])
def delete_document(doc_id):
    conn = get_db()
    conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/documents/<int:doc_id>/resolve", methods=["POST"])
def resolve_document(doc_id):
    data = request.get_json() or {}
    manual_id = (data.get("identifier") or "").strip()
    conn = get_db()
    doc = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    if not doc:
        conn.close()
        return jsonify({"error": "Not found"}), 404
    identifier = manual_id or doc["doi"] or doc["title"] or doc["filename"].replace(".pdf", "")
    if not identifier:
        conn.close()
        return jsonify({"error": "No identifier"}), 400
    print(f"Resolviendo documento #{doc_id}: '{identifier}'...", flush=True)
    try:
        result = resolve_any(identifier)
    except Exception as e:
        print(f"  ERROR resolviendo '{identifier}': {e}", flush=True)
        conn.close()
        return jsonify({"error": f"Error: {e}"}), 502
    if not result:
        print(f"  No se pudo resolver '{identifier}'", flush=True)
        conn.close()
        return jsonify({"error": "Could not resolve"}), 502
    conn.execute(
        "UPDATE documents SET title=?, author=?, year=?, doi=?, abstract=?, category=?, updated_at=? WHERE id=?",
        (result["title"], result["author"], result["year"], result["doi"],
         result.get("abstract"), result.get("category"), datetime.now().isoformat(), doc_id),
    )
    if result.get("abstract"):
        _, keywords = parse_abstract(result["abstract"])
        for kw in keywords:
            conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (kw,))
            tag = conn.execute("SELECT id FROM tags WHERE name = ?", (kw,)).fetchone()
            if tag:
                conn.execute("INSERT OR IGNORE INTO document_tags (document_id, tag_id) VALUES (?, ?)", (doc_id, tag[0]))
    cat = result.get("category")
    if cat:
        cat_name = ARXIV_CATEGORIES.get(cat, cat)
        conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (cat_name,))
        ct = conn.execute("SELECT id FROM tags WHERE name = ?", (cat_name,)).fetchone()
        if ct:
            conn.execute("INSERT OR IGNORE INTO document_tags (document_id, tag_id) VALUES (?, ?)", (doc_id, ct[0]))
    doc_type = detect_doc_type(result.get("doi"), result.get("title"), "")
    conn.execute("UPDATE documents SET doc_type=? WHERE id=?", (doc_type, doc_id))
    conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (doc_type,))
    tt = conn.execute("SELECT id FROM tags WHERE name = ?", (doc_type,)).fetchone()
    if tt:
        conn.execute("INSERT OR IGNORE INTO document_tags (document_id, tag_id) VALUES (?, ?)", (doc_id, tt[0]))
    conn.commit()
    conn.close()
    print(f"  -> {result['title'][:60]}", flush=True)
    return jsonify({**result, "ok": True})


@app.route("/api/resolve-all", methods=["POST"])
def resolve_all():
    if resolve_state["running"]:
        return jsonify({"error": "Already running"}), 409
    threading.Thread(target=resolve_existing_unresolved, daemon=True).start()
    return jsonify({"started": True})


@app.route("/api/resolve-progress")
def resolve_progress():
    return jsonify(resolve_state)


@app.route("/api/tags")
def get_tags():
    conn = get_db()
    tags = conn.execute("SELECT name FROM tags ORDER BY name").fetchall()
    conn.close()
    return jsonify([row["name"] for row in tags])


@app.route("/api/retag", methods=["POST"])
def retag_all():
    conn = get_db()
    conn.execute("DELETE FROM document_tags")
    conn.execute("DELETE FROM tags")
    docs = conn.execute("SELECT * FROM documents").fetchall()
    for d in docs:
        _retag_single(d, conn)
    conn.execute("DELETE FROM tags WHERE id NOT IN (SELECT DISTINCT tag_id FROM document_tags)")
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "documents": len(docs)})


def _retag_single(d, conn):
    text = d["abstract"]
    pdf_text = None
    if not text:
        pdf_text = extract_pdf_text(d["path"])
        if pdf_text:
            text = pdf_text
    _, keywords = parse_abstract(text) if text else (None, [])
    if not keywords and text:
        words = re.findall(r"[a-zA-Z]\w{3,}", text.lower())
        word_counts = {}
        for w in words:
            if w not in _STOPWORDS:
                word_counts[w] = word_counts.get(w, 0) + 1
        sorted_words = sorted(word_counts.items(), key=lambda x: -x[1])
        keywords = [w for w, c in sorted_words[:15] if len(w) > 3]
    conn.execute("DELETE FROM document_tags WHERE document_id = ?", (d["id"],))
    for kw in keywords:
        conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (kw,))
        t = conn.execute("SELECT id FROM tags WHERE name = ?", (kw,)).fetchone()
        if t:
            conn.execute("INSERT OR IGNORE INTO document_tags (document_id, tag_id) VALUES (?, ?)", (d["id"], t[0]))
    cat = d["category"]
    if cat:
        cat_name = ARXIV_CATEGORIES.get(cat, cat)
        conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (cat_name,))
        ct = conn.execute("SELECT id FROM tags WHERE name = ?", (cat_name,)).fetchone()
        if ct:
            conn.execute("INSERT OR IGNORE INTO document_tags (document_id, tag_id) VALUES (?, ?)", (d["id"], ct[0]))
    return keywords


@app.route("/api/documents/<int:doc_id>/retag", methods=["POST"])
def retag_document(doc_id):
    conn = get_db()
    d = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    if not d:
        conn.close()
        return jsonify({"error": "Not found"}), 404
    keywords = _retag_single(d, conn)
    conn.execute("DELETE FROM tags WHERE id NOT IN (SELECT DISTINCT tag_id FROM document_tags)")
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "tags": keywords})


@app.route("/api/documents/<int:doc_id>/tags", methods=["POST"])
def add_tag(doc_id):
    data = request.get_json()
    tag_name = data.get("tag", "").strip().lower()
    if not tag_name:
        return jsonify({"error": "Tag name required"}), 400
    conn = get_db()
    conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag_name,))
    tag_id = conn.execute("SELECT id FROM tags WHERE name = ?", (tag_name,)).fetchone()[0]
    conn.execute("INSERT OR IGNORE INTO document_tags (document_id, tag_id) VALUES (?, ?)", (doc_id, tag_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/documents/<int:doc_id>/tags/<tag_name>", methods=["DELETE"])
def remove_tag(doc_id, tag_name):
    conn = get_db()
    tag = conn.execute("SELECT id FROM tags WHERE name = ?", (tag_name,)).fetchone()
    if tag:
        conn.execute("DELETE FROM document_tags WHERE document_id = ? AND tag_id = ?", (doc_id, tag[0]))
        conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/scan", methods=["POST"])
def scan():
    count = scan_papers()
    return jsonify({"added": count})


@app.route("/api/dedup", methods=["POST"])
def dedup_endpoint():
    count = dedup()
    return jsonify({"removed": count})


@app.route("/api/open/<int:doc_id>")
def open_pdf(doc_id):
    conn = get_db()
    doc = conn.execute("SELECT path FROM documents WHERE id = ?", (doc_id,)).fetchone()
    conn.close()
    if doc:
        os.startfile(doc["path"])
        return jsonify({"ok": True})
    return jsonify({"error": "Not found"}), 404


@app.route("/api/graph")
def graph_data():
    try:
        conn = get_db()
        docs = conn.execute("SELECT id, title, author, year FROM documents ORDER BY title").fetchall()
        tag_links = conn.execute("""
            SELECT dt.document_id, t.name FROM document_tags dt
            JOIN tags t ON dt.tag_id = t.id
        """).fetchall()
        conn.close()

        doc_tags = {}
        for tl in tag_links:
            doc_tags.setdefault(tl["document_id"], set()).add(tl["name"])

        nodes = []
        node_ids = set()
        for d in docs:
            label = (d["title"] or d["author"] or f"Doc {d['id']}")[:30]
            nodes.append({"id": d["id"], "label": label, "title": d["title"] or "", "year": d["year"]})
            node_ids.add(d["id"])

        edges = []
        seen = set()
        shared_tags = {}
        for tl in tag_links:
            shared_tags.setdefault(tl["name"], []).append(tl["document_id"])
        for tag, ids in shared_tags.items():
            ids = sorted(set(ids))
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    a, b = ids[i], ids[j]
                    if a in node_ids and b in node_ids:
                        key = (min(a, b), max(a, b))
                        if key not in seen:
                            seen.add(key)
                            edges.append({"from": a, "to": b, "title": tag})

        return jsonify({"nodes": nodes, "edges": edges})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    print("HomeArxiv iniciando...", flush=True)
    init_db()
    scan_papers()
    print("Servidor web en http://localhost:5000", flush=True)
    threading.Thread(target=resolve_existing_unresolved, daemon=True).start()
    webbrowser.open("http://localhost:5000")
    app.run(debug=False, port=5000)
