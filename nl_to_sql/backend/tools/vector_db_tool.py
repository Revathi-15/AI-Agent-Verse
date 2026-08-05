# vector_db_tool.py — Vector store for query history + semantic search (local SQLite-backed)
#
# Uses a simple TF-IDF cosine similarity approach for local mode (no external API needed).
# Set VECTOR_DB_PROVIDER=pinecone in .env to use Pinecone cloud vector store.

import os
import json
import sqlite3
import math
from datetime import datetime
from collections import Counter

import pandas as pd
from backend.tools.base import BaseTool
from backend.database   import DB_PATH

_ENV = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"
)
from dotenv import load_dotenv
load_dotenv(_ENV)

PROVIDER = os.getenv("VECTOR_DB_PROVIDER", "local").lower()


# ── Local TF-IDF vectorizer (no external deps) ──────────────────────────────

def _tokenize(text: str) -> list[str]:
    import re
    return re.findall(r"[a-z0-9]+", text.lower())


def _tfidf_vector(tokens: list[str], vocab: list[str]) -> list[float]:
    tf   = Counter(tokens)
    total= len(tokens) or 1
    vec  = []
    for w in vocab:
        tf_w = tf.get(w, 0) / total
        vec.append(tf_w)
    return vec


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x*y for x, y in zip(a, b))
    na  = math.sqrt(sum(x*x for x in a))
    nb  = math.sqrt(sum(y*y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


# ── DB helpers ───────────────────────────────────────────────────────────────

def _ensure_vector_table():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS _vector_store (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            ts       TEXT,
            query    TEXT,
            sql      TEXT,
            reply    TEXT,
            table_n  TEXT,
            rows     INTEGER,
            tokens   TEXT    -- JSON list of tokens for similarity search
        )
    """)
    conn.commit()
    conn.close()


def store_query(query: str, sql: str, reply: str,
                table: str, rows: int) -> int:
    """Persist a query+result into the vector store. Returns the new row id."""
    _ensure_vector_table()
    tokens = json.dumps(_tokenize(query))
    conn   = sqlite3.connect(DB_PATH)
    cur    = conn.execute(
        "INSERT INTO _vector_store (ts, query, sql, reply, table_n, rows, tokens) "
        "VALUES (?,?,?,?,?,?,?)",
        (datetime.now().isoformat(timespec="seconds"), query, sql, reply, table, rows, tokens),
    )
    row_id = cur.lastrowid
    conn.commit()
    conn.close()
    return row_id


def semantic_search(query: str, top_k: int = 5) -> list[dict]:
    """Return the top_k most similar past queries using cosine TF-IDF similarity."""
    _ensure_vector_table()
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, ts, query, sql, reply, table_n, rows, tokens FROM _vector_store ORDER BY id DESC LIMIT 200"
    ).fetchall()
    conn.close()

    if not rows:
        return []

    q_tokens = _tokenize(query)

    # Build global vocabulary from all stored tokens + query
    all_tokens_list = [json.loads(r[7]) for r in rows] + [q_tokens]
    vocab = sorted(set(t for lst in all_tokens_list for t in lst))

    q_vec = _tfidf_vector(q_tokens, vocab)

    scored = []
    for r in rows:
        doc_tokens = json.loads(r[7])
        doc_vec    = _tfidf_vector(doc_tokens, vocab)
        score      = _cosine(q_vec, doc_vec)
        scored.append({
            "id"    : r[0],
            "ts"    : r[1],
            "query" : r[2],
            "sql"   : r[3],
            "reply" : r[4],
            "table" : r[5],
            "rows"  : r[6],
            "score" : round(score, 4),
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


class VectorDBTool(BaseTool):
    name        = "vector_search"
    description = "Search past queries semantically — 'show the report I made last week', retrieves similar historical queries"
    emoji       = "🔮"

    def run(self, table: str, df_store: dict,
            query: str = "",
            top_k: int = 5,
            **kwargs) -> dict:
        """
        Args:
            query: Natural language description of a past report.
            top_k: Number of similar results to return.
        """
        if not query:
            return {"ok": False, "summary": "Provide a search query.", "data": None}
        try:
            results = semantic_search(query, top_k=top_k)
            if not results:
                return {
                    "ok"     : True,
                    "summary": "No past queries found yet. Ask some questions first!",
                    "data"   : {"results": []},
                }

            top = results[0]
            summary = (
                f"🔮 Found **{len(results)}** similar past quer{'y' if len(results)==1 else 'ies'}.\n\n"
                f"Best match (similarity: {top['score']:.0%}): *\"{top['query']}\"* "
                f"— ran on `{top['table']}` at {top['ts']}, returned {top['rows']:,} rows."
            )
            return {
                "ok"     : True,
                "summary": summary,
                "data"   : {"results": results},
                "columns": ["score", "query", "sql", "table", "rows", "ts"],
                "rows"   : [
                    {
                        "score" : f"{r['score']:.0%}",
                        "query" : r["query"],
                        "sql"   : (r["sql"] or "")[:80] + "…" if r["sql"] and len(r["sql"])>80 else r["sql"],
                        "table" : r["table"],
                        "rows"  : r["rows"],
                        "ts"    : r["ts"],
                    }
                    for r in results
                ],
            }
        except Exception as e:
            return {"ok": False, "summary": f"Vector search failed: {e}", "data": None}
