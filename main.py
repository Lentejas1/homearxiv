import os
import sqlite3
from datetime import datetime

from flask import Flask, jsonify, render_template, request

PDF_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "papers")
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "papers.db")

app = Flask(__name__)


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
    conn.commit()
    conn.close()


def extract_pdf_metadata(path):
    try:
        import fitz
        doc = fitz.open(path)
        meta = doc.metadata
        title = meta.get("title", "").strip()
        author = meta.get("author", "").strip()
        year_str = ""
        if meta.get("creationDate"):
            import re
            m = re.search(r"D:(\d{4})", meta["creationDate"])
            if m:
                year_str = m.group(1)
        doc.close()
        return title or None, author or None, int(year_str) if year_str else None
    except ImportError:
        return None, None, None
    except Exception:
        return None, None, None


def scan_papers():
    conn = get_db()
    existing = {row["path"] for row in conn.execute("SELECT path FROM documents").fetchall()}
    new_count = 0
    if os.path.isdir(PDF_DIR):
        for fname in os.listdir(PDF_DIR):
            if fname.lower().endswith(".pdf"):
                fpath = os.path.join(PDF_DIR, fname)
                if fpath not in existing:
                    title, author, year = extract_pdf_metadata(fpath)
                    if not title:
                        title = os.path.splitext(fname)[0]
                    conn.execute(
                        "INSERT INTO documents (filename, title, author, year, path) VALUES (?, ?, ?, ?, ?)",
                        (fname, title, author, year, fpath),
                    )
                    new_count += 1
    conn.commit()
    conn.close()
    return new_count


# ─── API Routes ───────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/documents")
def get_documents():
    conn = get_db()
    search = request.args.get("search", "").strip()
    tag_filter = request.args.get("tag", "").strip()

    query = """
        SELECT d.*, GROUP_CONCAT(t.name, ', ') AS tags
        FROM documents d
        LEFT JOIN document_tags dt ON d.id = dt.document_id
        LEFT JOIN tags t ON dt.tag_id = t.id
    """
    params = []
    conditions = []

    if search:
        conditions.append("(d.title LIKE ? OR d.author LIKE ? OR d.filename LIKE ?)")
        params.extend([f"%{search}%"] * 3)

    if tag_filter:
        conditions.append("""
            d.id IN (
                SELECT dt2.document_id FROM document_tags dt2
                JOIN tags t2 ON dt2.tag_id = t2.id
                WHERE t2.name = ?
            )
        """)
        params.append(tag_filter)

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
    for key in ("title", "author", "year"):
        if key in data:
            fields.append(f"{key} = ?")
            params.append(data[key])
    if fields:
        fields.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        params.append(doc_id)
        conn.execute(
            f"UPDATE documents SET {', '.join(fields)} WHERE id = ?", params
        )
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


@app.route("/api/tags")
def get_tags():
    conn = get_db()
    tags = conn.execute("SELECT name FROM tags ORDER BY name").fetchall()
    conn.close()
    return jsonify([row["name"] for row in tags])


@app.route("/api/documents/<int:doc_id>/tags", methods=["POST"])
def add_tag(doc_id):
    data = request.get_json()
    tag_name = data.get("tag", "").strip().lower()
    if not tag_name:
        return jsonify({"error": "Tag name required"}), 400
    conn = get_db()
    conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag_name,))
    tag_id = conn.execute("SELECT id FROM tags WHERE name = ?", (tag_name,)).fetchone()[0]
    conn.execute(
        "INSERT OR IGNORE INTO document_tags (document_id, tag_id) VALUES (?, ?)",
        (doc_id, tag_id),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/documents/<int:doc_id>/tags/<tag_name>", methods=["DELETE"])
def remove_tag(doc_id, tag_name):
    conn = get_db()
    tag = conn.execute("SELECT id FROM tags WHERE name = ?", (tag_name,)).fetchone()
    if tag:
        conn.execute(
            "DELETE FROM document_tags WHERE document_id = ? AND tag_id = ?",
            (doc_id, tag[0]),
        )
        conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/scan", methods=["POST"])
def scan():
    count = scan_papers()
    return jsonify({"added": count})


@app.route("/api/open/<int:doc_id>")
def open_pdf(doc_id):
    conn = get_db()
    doc = conn.execute("SELECT path FROM documents WHERE id = ?", (doc_id,)).fetchone()
    conn.close()
    if doc:
        os.startfile(doc["path"])
        return jsonify({"ok": True})
    return jsonify({"error": "Not found"}), 404


if __name__ == "__main__":
    init_db()
    scan_papers()
    app.run(debug=True, port=5000)
