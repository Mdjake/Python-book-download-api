"""
╔══════════════════════════════════════════════════╗
║          LibGen Search API  –  FastAPI           ║
╚══════════════════════════════════════════════════╝

Requirements:
    pip install fastapi uvicorn libgen-api-enhanced

Run:
    uvicorn libgen_api:app --host 0.0.0.0 --port 8000

Endpoints:
    GET /search   – search books
    GET /help     – full documentation
"""

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
import asyncio
from concurrent.futures import ThreadPoolExecutor
from libgen_api_enhanced import LibgenSearch, SearchTopic
from collections import defaultdict
from typing import Optional, List

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="LibGen Search API",
    description="Search books, articles, and resources from LibGen databases.",
    version="1.0.0",
)

# ── Constants ─────────────────────────────────────────────────────────────────

MIRRORS = ["li","gz", "bz", "is"]

ALL_TOPICS = [
    SearchTopic.LIBGEN,
    SearchTopic.FICTION,
    SearchTopic.COMICS,
    SearchTopic.ARTICLES,
    SearchTopic.MAGAZINES,
    SearchTopic.STANDARDS,
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_size(size_str: str) -> float:
    try:
        return float(size_str.split()[0])
    except Exception:
        return 0.0


def _search_with_fallback(query, search_type, search_in, filters, exact_match):
    """Try all mirrors in order, return (results, mirror_used)."""
    last_err = None
    for mirror in MIRRORS:
        try:
            s = LibgenSearch(mirror=mirror)
            if filters:
                if search_type == "title":
                    results = s.search_title_filtered(query, filters, exact_match=exact_match, search_in=search_in)
                elif search_type == "author":
                    results = s.search_author_filtered(query, filters, exact_match=exact_match, search_in=search_in)
            else:
                if search_type == "title":
                    results = s.search_title(query, search_in=search_in)
                elif search_type == "author":
                    results = s.search_author(query, search_in=search_in)

            if results is not None:
                return results, mirror

        except Exception as e:
            last_err = e
            continue

    raise RuntimeError(f"All mirrors failed. Last error: {last_err}")


def _resolve_link(book):
    """Try HTTP link first, fall back to Tor link."""
    try:
        book.resolve_direct_download_link()
        link = book.resolved_download_link
        if link:
            return link, "http"
    except Exception:
        pass
    if book.tor_download_link:
        return book.tor_download_link, "tor"
    return None, None


def _deduplicate(results, max_per_title=2):
    seen = defaultdict(int)
    out = []
    for book in results:
        key = book.title.strip().lower()
        if seen[key] < max_per_title:
            seen[key] += 1
            out.append(book)
    return out


def _sort_results(results, sort: str):
    if sort == "size":
        return sorted(results, key=lambda b: _parse_size(b.size), reverse=True)
    elif sort == "year_new":
        return sorted(results, key=lambda b: b.year or "", reverse=True)
    elif sort == "year_old":
        return sorted(results, key=lambda b: b.year or "", reverse=False)
    return results  # relevance = original order


# ── Help page HTML ─────────────────────────────────────────────────────────────

HELP_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>LibGen API – Help</title>
<style>
  :root {
    --bg: #0a0a0f;
    --surface: #13131a;
    --surface2: #1c1c27;
    --border: #2a2a3a;
    --accent: #7c6af5;
    --accent2: #f5a623;
    --accent3: #4af0b0;
    --text: #e8e8f0;
    --muted: #6b6b85;
    --red: #f06060;
    --code-bg: #0d0d14;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Segoe UI', system-ui, sans-serif;
    padding: 40px 20px;
    line-height: 1.7;
  }
  body::before {
    content: '';
    position: fixed;
    inset: 0;
    background-image:
      linear-gradient(rgba(124,106,245,0.04) 1px, transparent 1px),
      linear-gradient(90deg, rgba(124,106,245,0.04) 1px, transparent 1px);
    background-size: 40px 40px;
    pointer-events: none;
    z-index: 0;
  }
  .wrap { max-width: 820px; margin: 0 auto; position: relative; z-index: 1; }
  h1 { font-size: 2.2rem; font-weight: 800; background: linear-gradient(135deg,#fff 30%,var(--accent));
       -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; margin-bottom: 8px; }
  .tagline { color: var(--muted); font-family: monospace; margin-bottom: 40px; }
  h2 { font-size: 1rem; font-weight: 700; color: var(--accent); letter-spacing: 2px;
       text-transform: uppercase; margin: 36px 0 12px; }
  p { color: var(--muted); margin-bottom: 10px; }
  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 22px 26px;
    margin-bottom: 16px;
    position: relative;
    overflow: hidden;
  }
  .card::before {
    content: ''; position: absolute; top:0; left:0; right:0; height:2px;
    background: linear-gradient(90deg, var(--accent), var(--accent3));
  }
  .param-name { color: var(--accent3); font-family: monospace; font-size: 1rem; font-weight: 700; }
  .param-type { color: var(--accent2); font-family: monospace; font-size: 0.8rem;
                background: rgba(245,166,35,0.1); border: 1px solid rgba(245,166,35,0.3);
                padding: 1px 7px; border-radius: 4px; margin-left: 8px; }
  .param-req  { color: var(--red); font-family: monospace; font-size: 0.75rem;
                background: rgba(240,96,96,0.1); border: 1px solid rgba(240,96,96,0.3);
                padding: 1px 7px; border-radius: 4px; margin-left: 6px; }
  .param-opt  { color: var(--muted); font-family: monospace; font-size: 0.75rem;
                background: rgba(107,107,133,0.1); border: 1px solid var(--border);
                padding: 1px 7px; border-radius: 4px; margin-left: 6px; }
  .param-desc { color: var(--muted); font-size: 0.88rem; margin: 10px 0 0; }
  .options { margin: 10px 0 0 0; padding: 0; list-style: none; }
  .options li { font-family: monospace; font-size: 0.83rem; color: var(--text);
                padding: 5px 0; border-bottom: 1px solid var(--border); }
  .options li:last-child { border: none; }
  .options li span { color: var(--accent3); }
  .code-block {
    background: var(--code-bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px 20px;
    font-family: monospace;
    font-size: 0.83rem;
    color: var(--accent3);
    margin: 10px 0;
    overflow-x: auto;
    white-space: pre;
    position: relative;
  }
  .copy-btn {
    position: absolute; top: 8px; right: 10px;
    background: none; border: 1px solid var(--border); color: var(--muted);
    font-size: 11px; font-family: monospace; padding: 3px 8px;
    border-radius: 4px; cursor: pointer; transition: all 0.2s;
  }
  .copy-btn:hover { border-color: var(--accent3); color: var(--accent3); }
  .json-block {
    background: var(--code-bg); border: 1px solid var(--border);
    border-radius: 8px; padding: 16px 20px; font-family: monospace;
    font-size: 0.82rem; overflow-x: auto; margin: 10px 0;
  }
  .jk { color: var(--accent); }   /* json key */
  .js { color: #c3e88d; }         /* json string */
  .jn { color: var(--accent2); }  /* json number */
  .tip { background: rgba(124,106,245,0.07); border: 1px solid rgba(124,106,245,0.25);
         border-radius: 8px; padding: 14px 18px; color: var(--muted); font-size: 0.87rem; margin: 8px 0; }
  .tip strong { color: var(--text); }
  .warn { background: rgba(240,96,96,0.07); border: 1px solid rgba(240,96,96,0.25);
          border-radius: 8px; padding: 14px 18px; color: var(--muted); font-size: 0.87rem; margin: 8px 0; }
  .warn strong { color: var(--red); }
  hr { border: none; border-top: 1px solid var(--border); margin: 36px 0; }
  footer { color: var(--muted); font-size: 0.78rem; font-family: monospace; margin-top: 48px; text-align: center; }
</style>
</head>
<body>
<div class="wrap">

  <h1>📚 LibGen Search API</h1>
  <p class="tagline"># search books · articles · journals · comics from Library Genesis</p>

  <hr/>

  <!-- ENDPOINT -->
  <h2>🔍 Endpoint</h2>
  <div class="card">
    <div style="font-family:monospace;font-size:1rem;">
      <span style="color:var(--accent3);">GET</span>
      <span style="color:#fff;margin-left:10px;">/search</span>
    </div>
    <p class="param-desc" style="margin-top:10px;">
      Returns a JSON list of books matching your query, with title, author, year, format, size, and download link.
    </p>
  </div>

  <hr/>

  <!-- REQUIRED -->
  <h2>🧠 Required Parameters</h2>

  <div class="card">
    <div>
      <span class="param-name">q</span>
      <span class="param-type">string</span>
      <span class="param-req">required</span>
    </div>
    <p class="param-desc">The search query — book title, author name, keyword</p>
    <div class="code-block"><button class="copy-btn" onclick="cp(this)">copy</button>/search?q=atomic habits</div>
  </div>

  <hr/>

  <!-- OPTIONAL -->
  <h2>⚙️ Optional Parameters</h2>

  <div class="card">
    <div>
      <span class="param-name">type</span>
      <span class="param-type">string</span>
      <span class="param-opt">optional</span>
    </div>
    <p class="param-desc">Controls which fields are matched during search.</p>
    <ul class="options">
      <li><span>"default"</span> — Search title + author + series + year — <em>default</em></li>
      <li><span>"title"</span> — Match only book titles</li>
      <li><span>"author"</span> — Match only author names</li>
    </ul>
    <div class="code-block"><button class="copy-btn" onclick="cp(this)">copy</button>/search?q=jane austen&type=author</div>
  </div>

  <div class="card">
    <div>
      <span class="param-name">limit</span>
      <span class="param-type">integer</span>
      <span class="param-opt">optional</span>
    </div>
    <p class="param-desc">Number of results to return. Default: <strong>10</strong>. Max recommended: 50.</p>
    <div class="code-block"><button class="copy-btn" onclick="cp(this)">copy</button>/search?q=python&limit=5</div>
  </div>

  <div class="card">
    <div>
      <span class="param-name">format</span>
      <span class="param-type">string</span>
      <span class="param-opt">optional</span>
    </div>
    <p class="param-desc">Filter by file format. Leave blank for all formats.</p>
    <ul class="options">
      <li><span>"pdf"</span> — PDF files</li>
      <li><span>"epub"</span> — EPUB (best for e-readers)</li>
      <li><span>"mobi"</span> — Kindle format</li>
      <li><span>"djvu"</span>, <span>"fb2"</span>, <span>"azw3"</span>, <span>"txt"</span> — Other formats</li>
    </ul>
    <div class="code-block"><button class="copy-btn" onclick="cp(this)">copy</button>/search?q=clean code&format=epub</div>
  </div>

  <div class="card">
    <div>
      <span class="param-name">year</span>
      <span class="param-type">string</span>
      <span class="param-opt">optional</span>
    </div>
    <p class="param-desc">Filter by publication year. Supports partial matching.</p>
    <ul class="options">
      <li><span>"2020"</span> — Exact year 2020</li>
      <li><span>"200"</span> — Matches any year containing "200" → 2000, 2001 … 2009</li>
      <li><span>"19"</span> — Matches any year in the 1900s</li>
    </ul>
    <div class="code-block"><button class="copy-btn" onclick="cp(this)">copy</button>/search?q=physics&year=2020</div>
  </div>

  <div class="card">
    <div>
      <span class="param-name">language</span>
      <span class="param-type">string</span>
      <span class="param-opt">optional</span>
    </div>
    <p class="param-desc">Filter by language of the book. Case-insensitive substring match.</p>
    <div class="code-block"><button class="copy-btn" onclick="cp(this)">copy</button>/search?q=physics&language=English</div>
  </div>

  <div class="card">
    <div>
      <span class="param-name">sort</span>
      <span class="param-type">string</span>
      <span class="param-opt">optional</span>
    </div>
    <p class="param-desc">Sort the result list.</p>
    <ul class="options">
      <li><span>"relevance"</span> — Default Libgen ordering — <em>default</em></li>
      <li><span>"size"</span> — Largest files first (usually best scan quality)</li>
      <li><span>"year_new"</span> — Newest publications first</li>
      <li><span>"year_old"</span> — Oldest publications first</li>
    </ul>
    <div class="code-block"><button class="copy-btn" onclick="cp(this)">copy</button>/search?q=deep learning&sort=year_new</div>
  </div>

  <hr/>

  <!-- RESPONSE -->
  <h2>📦 Response Format</h2>
  <div class="card">
    <p class="param-desc">The API returns JSON with the following structure:</p>
    <div class="json-block">{
  <span class="jk">"query"</span>: <span class="js">"python"</span>,
  <span class="jk">"mirror_used"</span>: <span class="js">"li"</span>,
  <span class="jk">"count"</span>: <span class="jn">10</span>,
  <span class="jk">"results"</span>: [
    {
      <span class="jk">"title"</span>:     <span class="js">"Learning Python"</span>,
      <span class="jk">"author"</span>:    <span class="js">"Mark Lutz"</span>,
      <span class="jk">"year"</span>:      <span class="js">"2013"</span>,
      <span class="jk">"language"</span>:  <span class="js">"English"</span>,
      <span class="jk">"format"</span>:    <span class="js">"pdf"</span>,
      <span class="jk">"size"</span>:      <span class="js">"18 Mb"</span>,
      <span class="jk">"pages"</span>:     <span class="js">"1540"</span>,
      <span class="jk">"link"</span>:      <span class="js">"https://..."</span>,
      <span class="jk">"link_type"</span>: <span class="js">"http"</span>,
      <span class="jk">"mirrors"</span>:   [<span class="js">"https://..."</span>, <span class="js">"https://..."</span>]
    }
  ]
}</div>
  </div>

  <hr/>

  <!-- EXAMPLES -->
  <h2>🚀 Example Requests</h2>

  <div class="card">
    <p class="param-desc" style="color:var(--text);font-weight:700;margin-bottom:8px;">Basic search</p>
    <div class="code-block"><button class="copy-btn" onclick="cp(this)">copy</button>/search?q=machine learning</div>
  </div>

  <div class="card">
    <p class="param-desc" style="color:var(--text);font-weight:700;margin-bottom:8px;">Search by title, PDF only, newest first</p>
    <div class="code-block"><button class="copy-btn" onclick="cp(this)">copy</button>/search?q=deep learning&type=title&format=pdf&sort=year_new</div>
  </div>

  <div class="card">
    <p class="param-desc" style="color:var(--text);font-weight:700;margin-bottom:8px;">Author search, English EPUBs only</p>
    <div class="code-block"><button class="copy-btn" onclick="cp(this)">copy</button>/search?q=george orwell&type=author&format=epub&language=English&limit=5</div>
  </div>

  <div class="card">
    <p class="param-desc" style="color:var(--text);font-weight:700;margin-bottom:8px;">Filter by decade (2000s)</p>
    <div class="code-block"><button class="copy-btn" onclick="cp(this)">copy</button>/search?q=physics&year=200&format=pdf</div>
  </div>

  <hr/>

  <!-- NOTES -->
  <h2>⚠️ Notes</h2>

  <div class="warn">
    <strong>Required:</strong> Only <code>q</code> is required. All other parameters are optional.
  </div>
  <div class="tip">
    <strong>Mirror fallback:</strong> The API automatically tries 3 Libgen mirrors (.li → .bz → .gs) if one is down. The <code>mirror_used</code> field in the response tells you which one responded.
  </div>
  <div class="tip">
    <strong>Download links:</strong> Links are resolved in real time. If a direct HTTP link can't be resolved, a Tor (.onion) link is returned instead. <code>link_type</code> tells you which one it is.
  </div>
  <div class="tip">
    <strong>Year filter:</strong> Year values are always strings — "2020" not 2020. Partial values like "200" do substring matching.
  </div>

  <hr/>

  <!-- TIPS -->
  <h2>🧩 Tips</h2>
  <div class="card">
    <ul class="options">
      <li>Start simple — just use <span>q</span>, add filters only when needed</li>
      <li>Smaller <span>limit</span> = faster response (link resolution takes time per result)</li>
      <li>If you get 0 results, try removing format/year/language filters first</li>
      <li>Use <span>type=author</span> when searching a person's name to avoid noise</li>
      <li>Use <span>sort=size</span> to get the highest-quality scan of a book</li>
    </ul>
  </div>

  <hr/>

  <footer>LibGen Search API · Built with FastAPI + libgen-api-enhanced · Use wisely.</footer>
</div>

<script>
function cp(btn) {
  const text = btn.parentElement.innerText.replace('copy','').trim();
  navigator.clipboard.writeText(text).then(() => {
    btn.textContent = 'copied!';
    setTimeout(() => btn.textContent = 'copy', 2000);
  });
}
</script>
</body>
</html>
"""

# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/help", response_class=HTMLResponse, tags=["Docs"])
def help_page():
    """Full HTML documentation for the API."""
    return HTMLResponse(content=HELP_HTML)


@app.get("/search", tags=["Search"])
def search_books(
    q: str = Query(..., description="Search query (title, author, keyword)"),
    type: Optional[str] = Query("title", description="Search type: title (default) | author"),
    limit: Optional[int] = Query(3, ge=1, le=100, description="Number of results (1–100)"),
    format: Optional[str] = Query(None, description="File format filter: pdf, epub, mobi, etc."),
    year: Optional[str] = Query(None, description="Year filter, e.g. 2020 or 200 for 2000s"),
    language: Optional[str] = Query(None, description="Language filter, e.g. English"),
    sort: Optional[str] = Query("relevance", description="Sort: relevance | size | year_new | year_old"),
):
    # ── Validate params ───────────────────────────────────────────────────────
    valid_types = {"title", "author"}
    if type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid type '{type}'. Use: title, author")

    valid_sorts = {"relevance", "size", "year_new", "year_old"}
    if sort not in valid_sorts:
        raise HTTPException(status_code=400, detail=f"Invalid sort '{sort}'. Use: {', '.join(valid_sorts)}")

    # ── Build filters ─────────────────────────────────────────────────────────
    filters = {}
    if format:
        filters["extension"] = format.lower()
    if year:
        filters["year"] = str(year)
    if language:
        filters["language"] = language

    # ── Search ────────────────────────────────────────────────────────────────
    try:
        raw_results, mirror_used = _search_with_fallback(
            query=q,
            search_type=type,
            search_in=ALL_TOPICS,
            filters=filters,
            exact_match=False,   # always fuzzy — friendlier for an API
        )
    except Exception as e:
        return JSONResponse(content={
            "query": q,
            "error": f"All mirrors failed: {str(e)}",
            "tip": "LibGen mirrors may be down. Try again later or check /help.",
            "mirrors_tried": MIRRORS
        }, status_code=503)

    if not raw_results:
        return JSONResponse(content={
            "query": q,
            "mirror_used": mirror_used,
            "count": 0,
            "results": [],
        })

    # ── Deduplicate + sort + slice ────────────────────────────────────────────
    results = _deduplicate(raw_results, max_per_title=2)
    results = _sort_results(results, sort)
    results = results[:limit]

    # ── Build response ────────────────────────────────────────────────────────
    output = []
    for book in results:
        link, link_type = _resolve_link(book)
        output.append({
            "title":     book.title     or "",
            "author":    book.author    or "",
            "year":      book.year      or "",
            "language":  book.language  or "",
            "format":    book.extension or "",
            "size":      book.size      or "",
            "pages":     book.pages     or "",
            "link":      link           or "",
            "link_type": link_type      or "",
        })

    return JSONResponse(content={
        "query": q,
        "count": len(output),
        "results": output,
    })


@app.get("/mirrors", tags=["Debug"])
def test_mirrors():
    """Debug endpoint to test mirror connectivity."""
    status = {}
    for mirror in MIRRORS:
        try:
            s = LibgenSearch(mirror=mirror)
            # Quick test search
            results = s.search_default("test", search_in=[SearchTopic.LIBGEN], max_results=1)
            status[mirror] = {"status": "ok", "results": len(results)}
        except Exception as e:
            status[mirror] = {"status": "failed", "error": str(e)[:100] + "..." if len(str(e)) > 100 else str(e)}
    return {"mirrors": status}

@app.get("/", tags=["Root"])
def root():
    return {
        "message": "LibGen Search API is running.",
        "docs":    "/help",
        "search":  "/search?q=your+query",
        "swagger": "/docs",
    }
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

