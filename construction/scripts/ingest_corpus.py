"""Ingest a corpus of PDFs, EPUBs and/or web pages into clean Markdown files.

The first stage of the healthcare file-search tool: normalize heterogeneous sources
(local PDFs, website URLs) into one Markdown corpus that a later step can chunk / embed.

Two ingestion paths, one per source kind:
  - PDF   → each page is rendered and transcribed to Markdown by a VISION model, which
            preserves the headings/tables/layout a text extractor
            flattens. A process-wide rate gate pauses ALL page calls when a 429 is seen and
            resumes once the limit resets, so a tight tokens/min cap throttles cleanly rather
            than failing. Per-page resilience: a page that still fails (content-policy 400 or
            exhausted retries) falls back to PyMuPDF's embedded text, so one bad page never
            fails the document. `--text-first` flips to the fast path (take the embedded text
            layer, VLM only for scanned pages) — far faster/cheaper for big born-digital PDFs.
  - EPUB  → spine documents are converted straight to Markdown from their XHTML. No vision
            model and no extraction heuristics, so conversion is fully deterministic.
  - Web   → trafilatura pulls the *main content* to Markdown and drops the boilerplate
            (nav, footer, "About us" / "Contact" / cookie banners), no LLM needed.

Each output file carries a small YAML frontmatter block (source, type, title) so the
downstream index keeps provenance. Idempotent: existing outputs are skipped unless
--overwrite. The PDF path needs an OpenAI-compatible vision endpoint; creds come from the
repo-root .env (JUDGE_BASE_URL / JUDGE_API_KEY are reused for it).

  # Deps (pymupdf, trafilatura) live in the workspace pyproject.toml — `uv sync` once.
  uv run python construction/scripts/ingest_corpus.py refs/guideline.pdf https://www.uptodate.com/...
  uv run python construction/scripts/ingest_corpus.py refs/ --out corpus/            # a dir → every *.pdf in it
  uv run python construction/scripts/ingest_corpus.py --from-file sources.txt        # one source per line
  uv run python construction/scripts/ingest_corpus.py refs/x.pdf --dpi 220 --overwrite
"""

from __future__ import annotations

import argparse
import base64
import datetime
import html
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from clinicare_core import load_env

SCRIPTS = Path(__file__).resolve().parent  # construction/scripts/
ROOT = SCRIPTS.parents[1]  # repo root

DEFAULT_MODEL = "anthropic/claude-sonnet-4-6"
# The corpus is assembled locally, not repo content (benchmark/corpus/README.md), so this writes
# to wherever CLINICARE_CORPUS_DIR points, falling back to a build dir. Output here
# will NOT be byte-identical to the published corpus — the PDF path transcribes pages with a
# vision model — so a regenerated corpus can't be used to reproduce published numbers.
DEFAULT_OUT = Path(os.environ.get("CLINICARE_CORPUS_DIR") or (ROOT / "corpus-build"))

# A page whose embedded text layer has at least this many words is transcribed directly
# (born-digital). Fewer → treated as scanned/image and sent to the vision LLM.
MIN_TEXT_WORDS = 10

# ...unless the page carries no images either, in which case it is not scanned, just sparse — a
# title or divider page. There is nothing for the model to transcribe, and asking it to return
# nothing is what produced echoed prompts and invented user turns in the corpus.
SPARSE_PAGE_WORDS = 12

PAGE_PROMPT = (
    "Transcribe this document page into clean GitHub-Flavored Markdown. "
    "Preserve the reading order, headings, lists, and tables (render tables as Markdown "
    "tables). Transcribe the text faithfully — do not summarize, translate, or invent "
    "content, and ignore pure page furniture (page numbers, running headers/footers). "
    "Output ONLY the Markdown for the page content, with no code fences and no commentary. "
    "If the page has no readable content, output nothing."
)


def slugify(text: str, fallback: str = "doc") -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return (s or fallback)[:80]


def is_url(ref: str) -> bool:
    return ref.startswith(("http://", "https://"))


def collect_sources(positional: list[str], from_file: str | None) -> list[tuple[str, str]]:
    """Expand CLI args into (kind, ref) pairs. A dir contributes every *.pdf under it."""
    refs = list(positional)
    if from_file:
        refs += [
            ln.strip()
            for ln in Path(from_file).read_text().splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")
        ]
    sources: list[tuple[str, str]] = []
    for ref in refs:
        if is_url(ref):
            sources.append(("web", ref))
            continue
        p = Path(ref)
        if p.is_dir():
            sources += [("pdf", str(f)) for f in sorted(p.glob("*.pdf"))]
        elif p.suffix.lower() == ".pdf":
            sources.append(("pdf", str(p)))
        elif p.suffix.lower() == ".epub":
            sources.append(("epub", str(p)))
        else:
            print(f"  ! skipping unrecognized source (not a URL, .pdf, .epub, or dir): {ref}")
    return sources


def _strip_fences(md: str) -> str:
    """Drop a ```markdown ... ``` wrapper if the model added one despite instructions."""
    md = md.strip()
    m = re.match(r"^```(?:markdown|md)?\s*\n(.*)\n```$", md, re.DOTALL)
    return m.group(1).strip() if m else md


def _is_rate_limit(exc: Exception) -> bool:
    s = str(exc)
    return "429" in s or "rate limit" in s.lower()


class _RateGate:
    """Process-wide pause shared by all page workers. On a 429 any worker calls trip(secs),
    which blocks every worker (parked in wait()) until the limit window resets — so a
    tokens/min cap throttles the whole run instead of each call failing on its own."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._open_at = 0.0  # time.monotonic() after which calls may resume

    def wait(self) -> None:
        while True:
            with self._lock:
                delay = self._open_at - time.monotonic()
            if delay <= 0:
                return
            time.sleep(min(delay, 5))

    def trip(self, seconds: float) -> None:
        with self._lock:
            self._open_at = max(self._open_at, time.monotonic() + seconds)


def _reset_delay(exc: Exception, default: float = 60.0) -> float:
    """Seconds to pause after a 429. Prefer the 'Limit resets at: <ts> UTC' in the error;
    else the token limit is per-minute, so default to 60s. Capped so a bad parse can't stall."""
    m = re.search(r"resets at:\s*([\d-]+ [\d:]+)\s*UTC", str(exc))
    if m:
        try:
            reset = datetime.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=datetime.timezone.utc
            )
            secs = (reset - datetime.datetime.now(datetime.timezone.utc)).total_seconds()
            if secs > 0:
                return min(secs + 2, 120)
        except ValueError:
            pass
    return default


def vlm_page_to_md(
    client, model: str, b64_png: str, gate: _RateGate, *, max_retries: int = 3
) -> str:
    """Transcribe a page image with the vision model. Honors the shared rate gate before every
    attempt; on a 429 it trips the gate (pausing ALL workers until the window resets) and retries.
    Non-rate-limit errors (e.g. a content-policy 400) raise for the caller to fall back on."""
    for attempt in range(max_retries):
        gate.wait()
        try:
            resp = client.chat.completions.create(
                model=model,
                temperature=0,
                max_tokens=8000,
                # Told to emit nothing for a blank page, a chat model tends to continue the
                # conversation instead — echoing the instruction or inventing the next user turn.
                # These stops end the completion before that text reaches the corpus.
                stop=["\nHuman:", "\nAssistant:", "Human: Transcribe this document"],
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": PAGE_PROMPT},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{b64_png}"},
                            },
                        ],
                    }
                ],
            )
            return _strip_fences(resp.choices[0].message.content or "")
        except Exception as exc:  # noqa: BLE001
            if _is_rate_limit(exc):
                delay = _reset_delay(exc)
                gate.trip(delay)  # pause every worker until the window resets
                print(f"    · 429 — pausing all page calls ~{int(delay)}s", flush=True)
                if attempt < max_retries - 1:
                    continue
            raise


def pdf_to_markdown(
    client, model: str, path: str, dpi: int, workers: int, text_first: bool = False
) -> tuple[str, str]:
    """Transcribe a PDF to Markdown. By default every page is sent to the vision model (best
    structure fidelity); with text_first, pages that already carry a real embedded text layer
    are taken verbatim and only scanned/image pages use the model.

    A process-wide _RateGate throttles all page calls together on a 429. Per page, a VLM failure
    (content-policy 400 or exhausted retries) falls back to the embedded text layer, so one bad
    page never fails the document. PyMuPDF isn't thread-safe on one Document, so page rendering
    is serialized under a lock (fast, local) while the VLM network calls run concurrently."""
    import pymupdf

    doc = pymupdf.open(path)
    mat = pymupdf.Matrix(dpi / 72, dpi / 72)
    n = doc.page_count
    doc_lock = threading.Lock()
    gate = _RateGate()
    results: list[str] = [""] * n
    stats = {"text": 0, "vlm": 0, "failed": 0}
    stats_lock = threading.Lock()

    def _bump(key: str) -> None:
        with stats_lock:
            stats[key] += 1

    def work(i: int) -> None:
        with doc_lock:  # PyMuPDF Document access serialized
            page = doc[i]
            text = page.get_text("text").strip()
            sparse = len(text.split()) < SPARSE_PAGE_WORDS and not page.get_images()
            use_text = sparse or (text_first and len(text.split()) >= MIN_TEXT_WORDS)
            b64 = (
                None
                if (use_text or client is None)
                else base64.b64encode(page.get_pixmap(matrix=mat).tobytes("png")).decode()
            )
        if b64 is None:  # text-first hit, or no client → take the text layer
            results[i] = text
            _bump("text")
            return
        try:
            md = vlm_page_to_md(client, model, b64, gate)
            results[i] = md if md.strip() else text
            _bump("vlm" if md.strip() else "text")
        except Exception as exc:  # noqa: BLE001 — content-policy / exhausted retries
            results[i] = text
            _bump("failed")
            print(
                f"    ! page {i + 1}: VLM failed ({type(exc).__name__}) — using text layer",
                flush=True,
            )

    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(work, range(n)))
    doc.close()

    note = f"{n} pages: {stats['vlm']} VLM, {stats['text']} text"
    if stats["failed"]:
        note += f" ({stats['failed']} VLM-failed → text fallback)"
    print(f"    · {note}", flush=True)

    body = "\n\n".join(r.strip() for r in results if r.strip())
    return Path(path).stem, body


def url_to_markdown(url: str) -> tuple[str, str]:
    """Fetch a page and extract the main content as Markdown, dropping boilerplate."""
    import trafilatura

    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        raise RuntimeError(f"could not fetch {url}")
    body = trafilatura.extract(
        downloaded,
        output_format="markdown",
        include_comments=False,
        include_tables=True,
        include_formatting=True,  # keep heading levels (##), bold, lists — not just bare paragraphs
    )
    if not body:
        raise RuntimeError(f"no main content extracted from {url}")
    body = re.sub(r"\[edit\]", "", body)  # strip wiki per-section "[edit]" link text

    title = None
    try:  # trafilatura's metadata parser is the primary title source
        from trafilatura.metadata import extract_metadata

        meta = extract_metadata(downloaded)
        title = getattr(meta, "title", None)
    except Exception:
        pass
    if not title:  # fall back to the raw <title> tag
        mt = re.search(r"<title[^>]*>(.*?)</title>", downloaded, re.I | re.S)
        title = html.unescape(mt.group(1).strip()) if mt else url
    return title, body


_EPUB_BLOCK = {
    "p",
    "div",
    "section",
    "article",
    "blockquote",
    "figcaption",
    "li",
    "tr",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
}


def _epub_spine(z) -> list[str]:
    """Content documents in reading order per the OPF spine, with nav/toc dropped.

    defusedxml, not stdlib ElementTree: the OPF comes from a publisher EPUB fetched over the
    network by acquire_corpus.py, so it is untrusted input, and unlike _epub_parse below there
    is no DOCTYPE stripping here to incidentally defuse an entity-expansion bomb."""
    import defusedxml.ElementTree as etree

    opf = next((n for n in z.namelist() if n.endswith(".opf")), None)
    if not opf:
        return [
            n for n in z.namelist() if n.endswith((".xhtml", ".html")) and "nav" not in n.lower()
        ]
    root = etree.fromstring(z.read(opf))
    ns = {"o": "http://www.idpf.org/2007/opf"}
    items = {i.get("id"): i for i in root.findall(".//o:manifest/o:item", ns)}
    base = opf.rsplit("/", 1)[0] + "/" if "/" in opf else ""
    out = []
    for ref in root.findall(".//o:spine/o:itemref", ns):
        item = items.get(ref.get("idref"))
        if item is None:
            continue
        href = item.get("href") or ""
        if (
            "nav" in (item.get("properties") or "")
            or "nav" in href.lower()
            or "toc" in href.lower()
        ):
            continue
        out.append(base + href)
    return [n for n in out if n in z.namelist()]


def _epub_parse(data: bytes):
    """XHTML → element tree with defusedxml. XHTML is XML by spec, but authors still use
    HTML named entities, which a plain XML parser rejects — so resolve those to characters first
    rather than taking on an lxml dependency for it.

    The DOCTYPE strip below is for those entities, not for safety; defusedxml is what makes an
    entity-expansion bomb in a downloaded EPUB a parse error instead of a hung maintainer."""
    import html as _html

    import defusedxml.ElementTree as etree

    text = data.decode("utf-8", "replace")
    text = re.sub(r"<!DOCTYPE[^>]*>", "", text, flags=re.I)
    text = re.sub(
        r"&(?!#|amp;|lt;|gt;|quot;|apos;)([A-Za-z][A-Za-z0-9]{1,31});",
        lambda m: _html.unescape(f"&{m.group(1)};"),
        text,
    )
    return etree.fromstring(text)


def _epub_md(el) -> str:
    """Recursive XHTML → Markdown. Deliberately explicit rather than extraction-based: an EPUB
    content document is already boilerplate-free, so trafilatura's main-content heuristic only
    costs headings and tables (measured: 0.90 vs 0.99 vocabulary coverage on the same file)."""
    raw = el.tag if isinstance(el.tag, str) else ""
    tag = raw.rsplit("}", 1)[-1].lower()
    text = (el.text or "") + "".join(_epub_md(c) for c in el)
    tail = el.tail or ""
    if tag in ("script", "style"):
        return tail
    if re.fullmatch(r"h[1-6]", tag):
        return f"\n\n{'#' * int(tag[1])} {text.strip()}\n\n" + tail
    if tag in ("strong", "b"):
        return f"**{text.strip()}**" + tail
    if tag in ("em", "i"):
        return f"*{text.strip()}*" + tail
    if tag == "sup":
        return f"<sup>{text.strip()}</sup>" + tail
    if tag == "br":
        return "\n" + tail
    if tag == "li":
        return f"\n- {text.strip()}" + tail
    if tag in ("td", "th"):
        return f" {text.strip()} |" + tail
    if tag == "tr":
        return "\n|" + text + tail
    if tag == "table":
        return "\n\n" + text + "\n\n" + tail
    if tag in _EPUB_BLOCK:
        return f"\n\n{text.strip()}\n\n" + tail
    return text + tail


def epub_to_markdown(path: str) -> tuple[str, str]:
    """(title, body) for an EPUB. Structured markup, so no vision model and no heuristics —
    the same input always yields the same Markdown."""
    import zipfile

    z = zipfile.ZipFile(path)
    title = ""
    opf = next((n for n in z.namelist() if n.endswith(".opf")), None)
    if opf:
        m = re.search(rb"<dc:title[^>]*>([^<]+)", z.read(opf))
        if m:
            title = m.group(1).decode("utf-8", "replace").strip()
    parts = []
    for name in _epub_spine(z):
        doc = _epub_parse(z.read(name))
        body = next(
            (
                e
                for e in doc.iter()
                if isinstance(e.tag, str) and e.tag.rsplit("}", 1)[-1] == "body"
            ),
            None,
        )
        parts.append(_epub_md(body if body is not None else doc))
    out = re.sub(r"[ \t]+", " ", "\n".join(parts))
    return (title or Path(path).stem), re.sub(r"\n{3,}", "\n\n", out).strip()


def _src_key(s: str) -> str:
    """Normalize a source string exactly as it's stored in frontmatter, so a re-run can match an
    already-ingested doc by its recorded `source` rather than by output filename — a web page's
    filename is a title slug that need not match the URL used to fetch it.

    A local path is reduced to its filename: these files are committed to a public repo, and the
    directory someone happened to run the script from is both meaningless to a reader and a
    disclosure of local layout."""
    key = str(s).replace('"', "'").replace("\n", " ").strip()
    return key if is_url(key) else Path(key).name


def _src_match(s: str) -> str:
    """Looser key for the already-ingested check: a local file is the same source however it was
    addressed, so match on its basename rather than on the path the caller happened to type."""
    key = _src_key(s)
    return key if is_url(key) else Path(key).name.lower()


def frontmatter(source: str, kind: str, title: str) -> str:
    return (
        "---\n"
        f'source: "{_src_key(source)}"\n'
        f"type: {kind}\n"
        f'title: "{_src_key(title)}"\n'
        "---\n\n"
    )


def unique_path(out_dir: Path, stem: str) -> Path:
    """First free <stem>.md / <stem>-2.md / ... in out_dir (collision-safe filenames)."""
    cand = out_dir / f"{stem}.md"
    n = 2
    while cand.exists():
        cand = out_dir / f"{stem}-{n}.md"
        n += 1
    return cand


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "sources", nargs="*", help="PDF paths, directories of PDFs, and/or http(s) URLs"
    )
    ap.add_argument("--from-file", help="text file with one source (path or URL) per line")
    ap.add_argument(
        "--out", type=Path, default=DEFAULT_OUT, help=f"output dir (default: {DEFAULT_OUT})"
    )
    ap.add_argument("--model", default=DEFAULT_MODEL, help="vision model for PDF pages")
    ap.add_argument("--dpi", type=int, default=200, help="PDF page render resolution")
    ap.add_argument("--workers", type=int, default=4, help="concurrent VLM page calls")
    ap.add_argument(
        "--text-first",
        action="store_true",
        help="fast path: take each page's embedded text layer, VLM only for scanned pages",
    )
    ap.add_argument(
        "--overwrite", action="store_true", help="re-ingest sources whose output exists"
    )
    args = ap.parse_args()

    sources = collect_sources(args.sources, args.from_file)
    if not sources:
        ap.error("no sources given (pass PDF paths / dirs / URLs, or --from-file)")

    args.out.mkdir(parents=True, exist_ok=True)

    # The vision client is only needed for PDFs; build it lazily so pure-URL runs need no creds.
    client = None
    if any(kind == "pdf" for kind, _ in sources):
        env = load_env()
        if not env.get("JUDGE_BASE_URL") or not env.get("JUDGE_API_KEY"):
            sys.exit("PDF ingestion needs JUDGE_BASE_URL + JUDGE_API_KEY in ../../.env")
        from openai import OpenAI

        client = OpenAI(base_url=env["JUDGE_BASE_URL"], api_key=env["JUDGE_API_KEY"])

    # Map already-ingested docs by their recorded `source`, so re-running the same source updates
    # its file in place instead of silently writing a duplicate (<slug>-2.md). Keyed on the source
    # (URL / path), NOT the output filename: a web page's filename is a title slug that need not
    # match the URL used for the existence check, which is why the old check duplicated on re-runs.
    existing_by_source: dict[str, Path] = {}
    for md in args.out.glob("*.md"):
        m = re.search(r'^source:\s*"(.*?)"\s*$', md.read_text(errors="replace"), re.MULTILINE)
        if m:
            existing_by_source[_src_match(m.group(1))] = md

    ok = 0
    for kind, ref in sources:
        prior = existing_by_source.get(_src_match(ref))
        if prior is not None and not args.overwrite:
            print(f"  = skip (already ingested): {prior.name}   [{ref}]")
            continue
        try:
            if kind == "pdf":
                title, body = pdf_to_markdown(
                    client, args.model, ref, args.dpi, args.workers, args.text_first
                )
            elif kind == "epub":
                title, body = epub_to_markdown(ref)
            else:
                title, body = url_to_markdown(ref)
        except Exception as e:  # one bad source shouldn't abort the whole corpus
            print(f"  ! FAILED {ref}: {e}")
            continue

        if prior is not None:  # same source seen before → overwrite its file in place
            dest = prior
        else:  # new source: PDFs keep their filename stem; web pages use the page title
            stem = (
                Path(ref).stem
                if kind in ("pdf", "epub")
                else slugify(title, fallback=slugify(ref.split("//", 1)[-1]))
            )
            dest = unique_path(args.out, stem)
        dest.write_text(frontmatter(ref, kind, title) + body.strip() + "\n")
        existing_by_source[_src_match(ref)] = dest  # so repeats within this same run dedupe too
        ok += 1
        print(f"  + {dest.name}  ({len(body.split())} words)   [{ref}]")

    print(f"\ningested {ok}/{len(sources)} source(s) → {args.out}")


if __name__ == "__main__":
    main()
