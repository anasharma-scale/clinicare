## Policy & guideline documents (`mimic` tools)

A curated corpus of clinical **policy / guideline documents** (society guidelines, consensus
statements, coding-compliance rules) is available through three read-only `mimic` MCP tools. Use
them to check what governing policy says and to **ground your decision in cited source text** — not
in unsourced recall.

> **Required for this task — do not skip.** This corpus is the governing standard: your determination
> has to rest on the applicable policy or guideline as written, not on patient data plus recall. The
> corpus is also where the **operational definition** of the criterion you are assessing generally
> lives: the thresholds, time windows, required elements, and exclusions that decide borderline
> cases. A guideline recalled from memory is not a substitute — versions differ, thresholds move, and
> a determination you cannot trace to a source is one the clinician relying on it cannot check.
>
> Work in this order, before you commit to a determination:
> 1. Call `list_policy_docs`, then `search_policy` to locate the governing guideline(s), then
>    `read_policy` to read the passage that **defines the criterion** — not merely one that mentions
>    the topic.
> 2. In your report's `## Method / criteria applied` section (see `## Final answer` for its required
>    contents), name each criterion you applied **together with the document and line span that
>    defines it**: `[policy: <doc> L<start>-L<end>]`. Write this section before the evidence and the
>    determination — the definition you retrieved is what you then apply to the record.
> 3. Attach an inline `[policy: <doc> L<start>-L<end>]` citation to **every claim that rests on
>    policy**, throughout the report.
> 4. If, after searching, **no document in the corpus governs this question**, say so explicitly in
>    `## Method / criteria applied` and list the searches you ran, so the next reader can see the
>    corpus was checked rather than skipped. Asserting that no policy applies without showing the
>    search is not a defensible basis for a determination.
>
> A determination that should rest on a governing standard but cites none is not reviewable: nobody
> downstream can tell which standard you applied, or whether you applied one at all. Cite the source
> even when your reading of the patient data is airtight.

- **`list_policy_docs(pattern?)`** — index of the corpus: filename, title, size. Start here.
- **`search_policy(query, regex?, case_sensitive?, context_lines?, max_results?)`** — search the
  corpus (like `grep`). Returns line-anchored matches `{doc, line, text}` with **physical line
  numbers**.
- **`read_policy(doc, line_start?, line_end?)`** — read a document, or a line range (like
  `cat`/`head`/`tail`). Returns the text with line-number prefixes.

Typical loop: `search_policy` to locate relevant passages → `read_policy` around a hit to read the
exact span → quote and cite it.

### Citing policy

When a claim in your report relies on a policy/guideline passage, cite it **inline** using the
document's exact filename and the line span you read, in this exact form:

```
[policy: <doc-filename> L<start>-L<end>]
```

Use the **complete, verbatim filename** exactly as the tools return it in the `doc` field —
including the full name and the `.md` extension. **Never abbreviate, shorten, or replace any part
of the filename with `…` or `...`**, even when the name is very long. The evaluation resolves each
citation by exact filename match, so a truncated or altered name will not resolve.

For example (note the full filename is reproduced in its entirety, however long):
`Iodinated contrast may be given without prophylaxis above this threshold [policy: davenport-et-al-2020-use-of-intravenous-iodinated-contrast-media-in-patients-with-kidney-disease-consensus-statements.md L128-L134].`

Cite the **narrowest line span** that actually supports the claim (the lines you read with
`read_policy`), so each citation resolves to the exact source text. Only cite passages you retrieved
from these tools — do not cite from memory.
