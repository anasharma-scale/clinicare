"""Convert a PhysioNet MIMIC-IV download into the Parquet tree the DuckDB backend reads.

    python -m mimic_tools.build_local --src ~/physionet --dst ~/mimic-parquet

Run once. Afterwards point MIMIC_DATA_ROOT at --dst. You must be credentialed on PhysioNet
for MIMIC-IV; this converts data you already have and downloads nothing.

WHY THIS EXISTS. The raw download is gzipped CSV, which cannot back the tool surface:
DuckDB can't push predicates into it, can't prune columns, and gzip isn't splittable, so a
patient-scoped query re-reads and re-decompresses the whole table — single-threaded — every
call. `chartevents` is ~433M rows and the benchmark issues ~100 tool calls per trial across
750 trials. Converting once turns each of those calls into a row-group-pruned local read.

THREE THINGS THIS DOES THAT A NAIVE `COPY … TO … (FORMAT PARQUET)` DOES NOT:

  1. Sorts by subject_id, so patient-scoped queries prune row groups instead of scanning the
     file. Measured against MIMIC-IV v3.1 this is a GUARANTEE, not a change: PhysioNet already
     ships every CSV ordered by subject_id, so the sort is a no-op on the current release. It
     stays because nothing upstream promises that ordering, and a release that arrived unsorted
     would silently destroy row-group pruning — the failure would look like "the benchmark got
     slow", not like a data problem. Cheap insurance, not the headline win.

  2. Infers types over the WHOLE file (sample_size=-1). DuckDB's CSV sniffer samples the head
     by default, and MIMIC has columns that look numeric for thousands of rows and then turn
     out to hold text — `labevents.value` carries "<0.1" and "GREATER THAN 50", for instance.
     A head-sampled schema silently drops or errors on those rows later, which surfaces as a
     wrong answer rather than a failure. The extra pass is worth it on a one-time conversion.

  3. Verifies what it wrote. Row counts are compared CSV-vs-Parquet per table, and the result
     is recorded in _manifest.json alongside each table's schema, so `--verify` can later
     confirm a tree is intact and unmodified without re-reading the source.

Memory: the big sorts spill to disk. --memory-limit and --temp-dir bound that; the defaults
are conservative enough for a laptop but slower than they need to be on a large machine.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from .db import TABLES

# NO per-column type overrides, deliberately. An earlier version pinned columns like
# labevents.value to VARCHAR on the theory that a sniffer might type them numerically and mangle
# the free-text rows ("<0.1", "UNABLE TO REPORT"). Checked against real MIMIC-IV v3.1, every one
# of those pins was either redundant or wrong:
#   * redundant — `sample_size=-1` reads the WHOLE file, so it cannot miss text that is present;
#     it already types labevents.value, chartevents.value, omr.result_value and the
#     microbiologyevents free-text columns as VARCHAR on its own.
#   * wrong — the ED vitals (temperature, heartrate, resprate, o2sat, sbp, dbp) are clean
#     numerics in the real data. Pinning them forced 12 columns to VARCHAR, which diverges from
#     the reference Parquet the published results were computed against and silently breaks any
#     numeric comparison in tool SQL.
# Whole-file inference is the protection. Do not reintroduce pins without checking the real file
# first; a wrong pin is worse than no pin, because it corrupts a column that was fine.

# Where the reader expects things, reused so the two can't drift: db.TABLES is the definition
# of which tables exist and which module each lives in.
MODULES = sorted({module for module, _ in TABLES.values()})


def find_source(src_roots: list[Path], module: str, table: str) -> Path | None:
    """Locate `<module>/<table>.csv[.gz]` under any --src root.

    Searched recursively because PhysioNet ships MIMIC-IV, MIMIC-IV-Note and MIMIC-IV-ED as
    three separate downloads with their own top-level version directories; people unpack them
    side by side, nested, or in three unrelated places. Matching on the parent directory name
    rather than the full path accommodates all of those.
    """
    for root in src_roots:
        for suffix in (".csv.gz", ".csv"):
            direct = root / module / f"{table}{suffix}"
            if direct.is_file():
                return direct
            for hit in sorted(root.rglob(f"{table}{suffix}")):
                if hit.parent.name == module:
                    return hit
    return None


def column_names(conn, source: Path) -> list[str]:
    """Column names only, from a cheap head sniff.

    Deliberately NOT `sample_size=-1`: we only want the header here, and making this the
    full-file pass would double the cost of every conversion for no benefit. Types come from
    the real read in convert_table.
    """
    rows = conn.execute(
        f"DESCRIBE SELECT * FROM read_csv('{source.as_posix()}', sample_size=1000) LIMIT 0"
    ).fetchall()
    return [r[0] for r in rows]


def _read_csv_expr(source: Path) -> str:
    """A read_csv(...) call that infers types from the WHOLE file, not a sampled head.

    `sample_size=-1` is the load-bearing argument. MIMIC has columns that look numeric for
    thousands of rows and then turn out to hold text — labevents.value carries "<0.1" and
    "GREATER THAN 50" — and a head-sampled schema drops or errors on those rows later, which
    surfaces as a wrong answer rather than a failure. It costs an extra pass over the file on a
    one-time conversion, which is a good trade.
    """
    return f"read_csv('{source.as_posix()}', sample_size=-1, header=true)"


def convert_table(conn, source: Path, dest: Path, module: str, table: str, row_group: int) -> dict:
    """Convert one table and return its manifest entry. Writes via a temp file and renames, so
    an interrupted run never leaves a truncated Parquet that a later run would treat as done."""
    cols = column_names(conn, source)
    reader = _read_csv_expr(source)

    # Sort by subject_id when the table has one. The dimension tables (d_items, d_labitems,
    # provider, caregiver, …) don't, and don't need it — they're small and read whole.
    order = " ORDER BY subject_id" if "subject_id" in cols else ""

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".parquet.part")
    conn.execute(
        f"COPY (SELECT * FROM {reader}{order}) TO '{tmp.as_posix()}' "
        f"(FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE {row_group})"
    )
    os.replace(tmp, dest)

    # Count from the source and the output independently. A mismatch means the conversion lost
    # rows — silently truncated data is the one failure that would look like a working dataset.
    #
    # Counting reads every row as VARCHAR on purpose. COUNT(*) doesn't care about types, and
    # reusing the sample_size=-1 reader here would repeat the whole-file inference pass — on
    # chartevents that is a second ~40 GB single-threaded decompress for no information. It is
    # also strictly more robust: an all-text read cannot fail on a type edge case, so the check
    # still runs on a file the typed read would have choked on.
    n_src = conn.execute(
        f"SELECT COUNT(*) FROM read_csv('{source.as_posix()}', all_varchar=true, header=true)"
    ).fetchone()[0]
    n_dst = conn.execute(f"SELECT COUNT(*) FROM read_parquet('{dest.as_posix()}')").fetchone()[0]
    if n_src != n_dst:
        dest.unlink(missing_ok=True)
        raise RuntimeError(
            f"{module}/{table}: wrote {n_dst} rows but the source has {n_src}. "
            "Output deleted; re-run. If it repeats, the source CSV may be truncated."
        )
    schema = conn.execute(f"DESCRIBE SELECT * FROM read_parquet('{dest.as_posix()}')").fetchall()
    return {
        "source": source.name,
        "rows": n_dst,
        "sorted_by": "subject_id" if order else None,
        "bytes": dest.stat().st_size,
        "schema": {r[0]: r[1] for r in schema},
    }


def verify(dst: Path) -> int:
    """Re-check an existing tree against its manifest. Returns a process exit code."""
    mpath = dst / "_manifest.json"
    if not mpath.is_file():
        print(f"no manifest at {mpath} — was this tree built by build_local?", file=sys.stderr)
        return 2
    manifest = json.loads(mpath.read_text())
    import duckdb

    conn = duckdb.connect()
    bad = 0
    for key, want in sorted(manifest["tables"].items()):
        module, table = key.split("/")
        p = dst / module / f"{table}.parquet"
        if not p.is_file():
            print(f"  MISSING  {key}")
            bad += 1
            continue
        n = conn.execute(f"SELECT COUNT(*) FROM read_parquet('{p.as_posix()}')").fetchone()[0]
        got = {
            r[0]: r[1]
            for r in conn.execute(
                f"DESCRIBE SELECT * FROM read_parquet('{p.as_posix()}')"
            ).fetchall()
        }
        if n != want["rows"]:
            print(f"  ROWS     {key}: {n} != {want['rows']}")
            bad += 1
        elif got != want["schema"]:
            drift = {
                k for k in set(got) | set(want["schema"]) if got.get(k) != want["schema"].get(k)
            }
            print(f"  SCHEMA   {key}: {sorted(drift)}")
            bad += 1
    conn.close()
    print(f"\n{len(manifest['tables']) - bad}/{len(manifest['tables'])} tables verified")
    return 1 if bad else 0


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--src",
        type=Path,
        action="append",
        default=[],
        help="a PhysioNet download root (repeatable — MIMIC-IV, -Note and -ED ship separately)",
    )
    ap.add_argument("--dst", type=Path, help="output Parquet root; point MIMIC_DATA_ROOT here")
    ap.add_argument("--tables", nargs="*", help="logical table name(s) to convert (default: all)")
    ap.add_argument("--overwrite", action="store_true", help="reconvert tables already present")
    ap.add_argument(
        "--verify", action="store_true", help="check an existing --dst, convert nothing"
    )
    ap.add_argument(
        "--memory-limit",
        default=os.environ.get("MIMIC_BUILD_MEMORY_LIMIT", "8GB"),
        help="DuckDB memory ceiling; the big sorts spill past it to --temp-dir (default 8GB)",
    )
    ap.add_argument(
        "--temp-dir",
        type=Path,
        default=None,
        help="spill directory for sorting (default: <dst>/.tmp). Needs tens of GB free for "
        "chartevents; put it on a fast disk if you can.",
    )
    ap.add_argument("--row-group-size", type=int, default=122880, help="Parquet row group rows")
    ap.add_argument("--dry-run", action="store_true", help="report what would be converted")
    args = ap.parse_args()

    if not args.dst:
        ap.error("--dst is required")
    if args.verify:
        raise SystemExit(verify(args.dst))
    if not args.src:
        ap.error("--src is required (repeatable)")

    src_roots = [p.expanduser().resolve() for p in args.src]
    for r in src_roots:
        if not r.is_dir():
            ap.error(f"--src is not a directory: {r}")
    dst = args.dst.expanduser().resolve()

    wanted = set(args.tables) if args.tables else None
    if wanted:
        unknown = wanted - set(TABLES)
        if unknown:
            ap.error(f"unknown table(s): {sorted(unknown)}. Known: {', '.join(sorted(TABLES))}")

    # Resolve every source up front so a missing download is reported once, before any work,
    # rather than an hour in. Note and ED are separate PhysioNet projects and are the ones
    # people most often forget.
    plan, missing = [], []
    for logical, (module, table) in sorted(TABLES.items()):
        if wanted and logical not in wanted:
            continue
        out = dst / module / f"{table}.parquet"
        found = find_source(src_roots, module, table)
        if found is None:
            missing.append(f"{module}/{table}")
        elif out.is_file() and not args.overwrite:
            print(f"  skip     {module}/{table} (exists; --overwrite to redo)")
        else:
            plan.append((found, out, module, table))

    if missing:
        mods = sorted({m.split("/")[0] for m in missing})
        print(
            f"\n{len(missing)} source file(s) not found under {[str(r) for r in src_roots]}:\n"
            f"  {', '.join(missing[:8])}{' …' if len(missing) > 8 else ''}\n"
            f"  affected module(s): {', '.join(mods)}\n"
            "  MIMIC-IV (hosp/icu), MIMIC-IV-Note (note) and MIMIC-IV-ED (ed) are three separate\n"
            "  PhysioNet downloads — pass each with its own --src, or one parent containing all.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    if args.dry_run:
        for source, out, module, table in plan:
            print(f"  would convert {module}/{table:22s} <- {source}")
        print(f"\n{len(plan)} table(s) to convert")
        return
    if not plan:
        print("nothing to do (everything already converted; --overwrite to redo)")
        return

    import duckdb

    temp_dir = (args.temp_dir or (dst / ".tmp")).expanduser()
    temp_dir.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect()
    conn.execute(f"SET memory_limit='{args.memory_limit}'")
    conn.execute(f"SET temp_directory='{temp_dir.as_posix()}'")
    # The sort is the memory-hungry step and we are writing to a fresh file, so nothing depends
    # on input order being preserved through the pipeline; turning that off lets DuckDB stream
    # the write instead of buffering it.
    conn.execute("SET preserve_insertion_order=false")

    manifest_path = dst / "_manifest.json"
    manifest = (
        json.loads(manifest_path.read_text())
        if manifest_path.is_file()
        else {"mimic_tools_build": 1, "tables": {}}
    )

    # Sequential on purpose: DuckDB already parallelizes within a single COPY, and running
    # several big sorts at once just multiplies peak memory against one shared limit.
    failed = []
    for i, (source, out, module, table) in enumerate(plan, 1):
        label = f"{module}/{table}"
        print(f"[{i}/{len(plan)}] {label:30s} ", end="", flush=True)
        t0 = time.monotonic()
        try:
            entry = convert_table(conn, source, out, module, table, args.row_group_size)
        except Exception as exc:  # noqa: BLE001 — report and continue; summary exits non-zero
            print(f"FAILED: {exc}")
            failed.append(label)
            continue
        manifest["tables"][label] = entry
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        mb = entry["bytes"] / 1e6
        srt = "" if entry["sorted_by"] else " (unsorted: no subject_id)"
        print(f"{entry['rows']:>12,} rows  {mb:>8.1f} MB  {time.monotonic() - t0:>6.1f}s{srt}")

    conn.close()
    try:
        temp_dir.rmdir()  # only if empty; a spill left behind is worth noticing
    except OSError:
        pass

    print(f"\nwrote {len(plan) - len(failed)}/{len(plan)} tables to {dst}")
    if failed:
        print(f"FAILED: {', '.join(failed)}", file=sys.stderr)
        raise SystemExit(1)
    print(f"manifest: {manifest_path}")
    print(f"\nSet MIMIC_DATA_ROOT={dst}")


if __name__ == "__main__":
    main()
