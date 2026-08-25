"""Assemble the policy corpus from benchmark/corpus_manifest.csv.

The corpus is 67 documents under mixed terms, so there is no single archive to hand out. Each
row carries an ``action`` saying how that document is obtained, and this script executes all of
them into one directory:

  ship-md        copied from benchmark/corpus_public/ (US government work, committed to the repo)
  fetch-pdf      downloaded, hash-checked, transcribed by the vision model
  fetch-html     fetched and extracted with trafilatura
  download-pdf   YOU download in a browser -- the publisher blocks scripted access
  download-epub  same, but choose EPUB in the viewer's download menu

Hand-downloaded files go in an inbox directory and are matched BY CONTENT HASH, so their
filenames do not matter. Re-run as often as you like: documents already built are skipped, so
the manual half can be completed a few files at a time.

  cd <repo root>
  uv run python construction/scripts/acquire_corpus.py --list-downloads   # what to fetch by hand
  uv run python construction/scripts/acquire_corpus.py                    # build everything else
  uv run python construction/scripts/acquire_corpus.py --inbox ~/Downloads

Output goes to $CLINICARE_CORPUS_DIR (else corpus-build/). Finishes by running
validate_policy_facts.py, which fails the build if a conversion dropped a load-bearing fact.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import http.client
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ingest_corpus import (  # noqa: E402
    epub_to_markdown,
    frontmatter,
    pdf_to_markdown,
    url_to_markdown,
)

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parents[1]
MANIFEST = ROOT / "benchmark" / "corpus_manifest.csv"
PUBLIC = ROOT / "benchmark" / "corpus_public"
VALIDATOR = ROOT / "benchmark" / "eval" / "gold" / "validate_policy_facts.py"
DEFAULT_OUT = Path(os.environ.get("CLINICARE_CORPUS_DIR") or (ROOT / "corpus-build"))

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0 Safari/537.36"
)
MANUAL = {"download-pdf", "download-epub"}

# A vision model can echo its own instructions, narrate the page image, or confabulate filler
# instead of transcribing. That text then reads as authoritative policy to a benchmark agent, so
# it must never reach the corpus.
ARTIFACTS = [
    ("prompt echo", re.compile(r"^\s*(Human|Assistant):\s", re.M)),
    ("instruction leak", re.compile(r"Transcribe this document page", re.I)),
    ("image narration", re.compile(r"!\[Image of page|The image shows a document page", re.I)),
    ("assistant voice", re.compile(r"^\s*(As an AI|I cannot|I am unable|Sorry, I)", re.I | re.M)),
    ("code fence leak", re.compile(r"^\s*```markdown", re.M)),
]


def artifacts(body: str) -> list[str]:
    return [name for name, rx in ARTIFACTS if rx.search(body)]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rows() -> list[dict]:
    if not MANIFEST.exists():
        sys.exit(f"manifest not found: {MANIFEST}")
    return list(csv.DictReader(MANIFEST.open()))


def download(url: str, timeout: int = 90, attempts: int = 3) -> bytes:
    """Fetch with retries: over ~30 downloads a truncated read or a reset connection is routine,
    and one flaky socket should not fail an otherwise good build."""
    last: Exception | None = None
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except (urllib.error.URLError, http.client.HTTPException, OSError) as e:
            last = e
            if isinstance(e, urllib.error.HTTPError) and e.code < 500:
                raise  # 403/404 are answers, not glitches
            time.sleep(2 * (i + 1))
    raise last if last else RuntimeError(f"could not fetch {url}")


DOI_RX = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+")


def _doi(text: str) -> str:
    m = DOI_RX.search(text or "")
    return re.sub(r"[.,;:)\]]+$", "", m.group()).lower() if m else ""


_DOI_WARNED: list = []


def _file_doi(path: Path) -> str:
    """The DOI printed inside a downloaded file. Publishers name downloads after the article
    ('perman-et-al-2023-….pdf'), which matches neither our corpus slug nor the URL, so the
    embedded DOI is the only identifier common to both sides."""
    try:
        if path.suffix.lower() == ".epub":
            import zipfile

            z = zipfile.ZipFile(path)
            opf = next((n for n in z.namelist() if n.endswith(".opf")), None)
            return _doi(z.read(opf).decode("utf-8", "replace")) if opf else ""
        import pymupdf

        doc = pymupdf.open(path)
        text = " ".join(doc[i].get_text() for i in range(min(2, doc.page_count)))
        doc.close()
        return _doi(text)
    except ImportError:
        # Without this, inbox matching quietly degrades to hash/filename and reports files that
        # are sitting right there as missing.
        if not _DOI_WARNED:
            _DOI_WARNED.append(1)
            print(
                "  ! pymupdf missing — cannot read DOIs from inbox PDFs; run `uv sync --extra construction`"
            )
        return ""
    except Exception:
        return ""


def index_inbox(inbox: Path) -> tuple[dict[str, Path], dict[str, Path]]:
    """({sha256: path}, {doi: path}) for every file in the inbox, so a hand-downloaded file can
    be identified by content rather than by whatever the browser called it."""
    by_hash: dict[str, Path] = {}
    by_doi: dict[str, Path] = {}
    if not inbox.is_dir():
        return by_hash, by_doi
    for p in sorted(inbox.rglob("*")):
        if p.is_file() and p.suffix.lower() in (".pdf", ".epub"):
            by_hash[sha256(p.read_bytes())] = p
            d = _file_doi(p)
            if d:
                by_doi.setdefault(d, p)
    return by_hash, by_doi


def _is_current(row: dict, dest: Path) -> bool:
    """True if `dest` was built from the source the manifest names now. Without this an output
    lingers after a manifest hash changes or a committed document is updated, and only
    --overwrite would ever replace it."""
    if row["action"] == "ship-md":
        src = PUBLIC / row["filename"]
        return src.exists() and src.read_bytes() == dest.read_bytes()
    head = dest.read_text(errors="replace")[:2000]
    key = row["source_sha256"]
    if not key:
        # No stable artifact to hash (web pages, an EPUB not yet downloaded). The URL it was
        # built from is still recorded, so at least a manifest re-point forces a rebuild. Live
        # drift at an unchanged URL is not detectable here — that is what the content
        # assertions and a periodic --overwrite are for.
        m = re.search(r'^source:\s*"([^"]*)"', head, re.M)
        return bool(m and m.group(1) == row["source_url"])
    m = re.search(r"^built_from:\s*(\S+)", head, re.M)
    return bool(m and m.group(1) == key)


def convert(kind: str, src: str, client, model: str, dpi: int, workers: int, text_first: bool):
    """(title, body) for one source, dispatched on the manifest's source_type."""
    if kind == "epub":
        return epub_to_markdown(src)
    if kind == "web":
        return url_to_markdown(src)
    return pdf_to_markdown(client, model, src, dpi, workers, text_first)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="corpus output directory")
    ap.add_argument(
        "--inbox",
        type=Path,
        default=ROOT / "corpus-inbox",
        help="directory holding hand-downloaded PDFs/EPUBs (matched by hash)",
    )
    ap.add_argument("--list-downloads", action="store_true", help="print the manual list and exit")
    ap.add_argument("--overwrite", action="store_true", help="rebuild documents already present")
    ap.add_argument(
        "--only",
        nargs="+",
        metavar="SUBSTR",
        help="build only documents whose filename contains one of these — a cheap way to exercise "
        "the conversion path without transcribing every page of the corpus",
    )
    ap.add_argument("--skip-validate", action="store_true", help="do not run the content check")
    ap.add_argument(
        "--verify-only",
        action="store_true",
        help="fetch, hash-check and match the inbox, but do not convert — exercises acquisition "
        "without ~2000 vision-model page calls",
    )
    ap.add_argument("--model", default=None, help="vision model for PDF transcription")
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--text-first", action="store_true", help="use the embedded PDF text layer")
    args = ap.parse_args()

    man = rows()
    if args.only:
        man = [r for r in man if any(k.lower() in r["filename"].lower() for k in args.only)]
        if not man:
            sys.exit(f"--only matched no documents: {args.only}")

    def _needed(r: dict) -> bool:
        dest = args.out / r["filename"]
        return args.overwrite or not dest.exists() or not _is_current(r, dest)

    todo = [r for r in man if _needed(r)]

    if args.list_downloads:
        pend = [r for r in todo if r["action"] in MANUAL]
        if not pend:
            print("nothing to download by hand — every manual document is already built")
            return 0
        print(f"Download these {len(pend)} files in a browser, then save them to {args.inbox}")
        print(
            "Each is governed by its publisher's terms; complying with them is your responsibility."
        )
        # grouped by action: the EPUBs need a format choice in a viewer, the PDFs download
        # straight through, so doing them in blocks avoids switching modes 19 times
        n = 0
        for act, head in (
            ("download-pdf", "PDFs — the link downloads the file directly"),
            (
                "download-epub",
                "EPUBs — the link opens a viewer; use its download menu and pick EPUB",
            ),
        ):
            group = [r for r in pend if r["action"] == act]
            if not group:
                continue
            print(f"\n{head}  ({len(group)})\n")
            for r in group:
                n += 1
                # our copy's size: close enough to set expectations before a slow download
                mb = int(r["source_bytes"] or 0) / 1048576
                size = (
                    f"  (~{mb:.0f} MB)" if mb >= 1 else (f"  (~{mb * 1024:.0f} KB)" if mb else "")
                )
                print(f"  {n:2}. {r['title'][:74]}{size}")
                print(f"      {r['source_url']}\n")
        print("Filenames do not matter — files are matched by content hash.")
        return 0

    args.out.mkdir(parents=True, exist_ok=True)
    inbox, inbox_doi = index_inbox(args.inbox)

    client = None
    if not args.verify_only and any(
        r["source_type"] == "pdf" and r["action"] != "ship-md" for r in todo
    ):
        from clinicare_core import load_env
        from openai import OpenAI

        env = load_env()
        if not env.get("JUDGE_BASE_URL") or not env.get("JUDGE_API_KEY"):
            sys.exit("PDF transcription needs JUDGE_BASE_URL + JUDGE_API_KEY in .env")
        client = OpenAI(base_url=env["JUDGE_BASE_URL"], api_key=env["JUDGE_API_KEY"])
    model = args.model or "anthropic/claude-sonnet-4-6"

    built = skipped = failed = 0
    missing: list[dict] = []
    drift: list[str] = []

    for r in man:
        name, action = r["filename"], r["action"]
        dest = args.out / name
        if not _needed(r):
            skipped += 1
            continue

        try:
            if action == "ship-md":
                src = PUBLIC / name
                if not src.exists():
                    print(f"  ! {name}: missing from {PUBLIC}")
                    failed += 1
                    continue
                if args.verify_only:
                    print(f"  = {name}  (public domain, present)")
                    built += 1
                    continue
                shutil.copy2(src, dest)
                print(f"  = {name}  (public domain, copied)")
                built += 1
                continue

            if action in MANUAL:
                want = r["source_sha256"]
                path = inbox.get(want) if want else None
                if path is None:
                    # A watermarked document never matches our hash and a first download has no
                    # hash yet, so fall back to the DOI carried by both the URL and the file.
                    path = inbox_doi.get(_doi(r["source_url"]))
                if path is None:
                    url_stem = Path(urllib.parse.urlparse(r["source_url"]).path).stem.lower()
                    if url_stem:
                        path = next(
                            (p for p in inbox.values() if p.stem.lower().startswith(url_stem)), None
                        )
                if path is None:
                    missing.append(r)
                    continue
                blob = path.read_bytes()
                if want and r["verify_method"] == "sha256" and sha256(blob) != want:
                    drift.append(f"{name}: inbox file does not match source_sha256")
                src_ref = str(path)
            else:  # fetch-pdf / fetch-html
                if r["source_type"] == "web":
                    src_ref = r["source_url"]
                else:
                    blob = download(r["source_url"])
                    got = sha256(blob)
                    if (
                        r["verify_method"] == "sha256"
                        and r["source_sha256"]
                        and got != r["source_sha256"]
                    ):
                        # a rolling URL can serve a revised file; the content check below is
                        # what decides whether the difference actually matters
                        drift.append(f"{name}: fetched bytes differ from source_sha256")
                    tmp = args.out / f".{name}.download"
                    tmp.write_bytes(blob)
                    src_ref = str(tmp)

            if args.verify_only:
                tmp = args.out / f".{name}.download"
                if tmp.exists():
                    tmp.unlink()
                how = {
                    "sha256": "hash ok",
                    "committed": "committed",
                    "content-assertions": "no hash (content-checked at build)",
                    "not-required": "no hash (non-governing)",
                }.get(r["verify_method"], "?")
                print(f"  ✓ {name}  ({r['action']}, {how})")
                built += 1
                continue

            title, body = convert(
                r["source_type"], src_ref, client, model, args.dpi, args.workers, args.text_first
            )
            found = artifacts(body)
            if found:
                print(f"  ! {name}: transcription artifacts ({', '.join(found)}) — not written")
                failed += 1
                continue
            fm = frontmatter(r["source_url"], r["source_type"], r["title"] or title)
            key = r["source_sha256"]
            if key:  # stamp the source, so a manifest change invalidates this output
                fm = fm.replace("---\n\n", f"built_from: {key}\n---\n\n", 1)
            dest.write_text(fm + body.strip() + "\n")
            tmp = args.out / f".{name}.download"
            if tmp.exists():
                tmp.unlink()
            print(f"  + {name}  ({len(body.split())} words, {action})")
            built += 1
        except Exception as e:  # one bad document must not abort the build
            print(f"  ! {name}: {type(e).__name__}: {str(e)[:110]}")
            failed += 1

    print(f"\nbuilt {built}, already present {skipped}, failed {failed} → {args.out}")
    if drift:
        print(f"\n{len(drift)} document(s) differ from the recorded hash:")
        for d in drift:
            print(f"  ~ {d}")
        print("  (the content check below decides whether the difference matters)")
    if missing:
        print(f"\n{len(missing)} document(s) still need a manual download → {args.inbox}")
        for r in missing:
            extra = "   << choose EPUB" if r["action"] == "download-epub" else ""
            print(f"  · {r['title'][:66]}{extra}")
            print(f"      {r['source_url']}")
        print("\n  re-run this script once they are saved; finished documents are skipped")

    if args.skip_validate or args.verify_only:
        if args.verify_only:
            print("\n--verify-only: nothing was converted, so the content check was not run")
        return 1 if (failed or missing) else 0
    print("\n── content check ─────────────────────────────────────────────")
    cmd = [sys.executable, str(VALIDATOR), "--corpus", str(args.out)]
    if args.only or missing:
        cmd.append("--present-only")  # a partial corpus: check what is there, list what is not
    rc = subprocess.run(cmd, check=False).returncode
    if missing:
        print(
            f"\nincomplete: {len(missing)} document(s) not yet downloaded — the check above only "
            f"covers what is present"
        )
    return rc or (1 if (failed or missing) else 0)


if __name__ == "__main__":
    raise SystemExit(main())
