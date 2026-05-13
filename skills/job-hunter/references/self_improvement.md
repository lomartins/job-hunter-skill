# Self-improvement loop

When `apply` hits a URL with no matching adapter, `learn.py` fires. Goal: never block the user, always leave a starting-point adapter, surface it for human review.

## Platform signature

The signature is what we use to detect "same kind of form" across hosts. Computed from:

1. Lowercased class list on the outermost `<form>` element (alphabetically sorted).
2. Framework hint, derived from page-level markers: `data-react-helmet`, `data-ember-action`, `ng-version`, `data-livewire-id`, `data-turbo-stream`. We take the first match.
3. Sorted list of input `name` attributes (or `id` if `name` missing).
4. URL path template: host preserved, then path segments with integer-only segments replaced by `:id` and known UUID-shaped segments replaced by `:uuid`.

Hash: SHA-256 of `"\n".join([class_list, framework, input_names, path_template])`, truncated to 16 hex chars.

Example: a Gupy form at `https://nubank.gupy.io/jobs/4392838/apply` with inputs `[name, email, cpf, phone, linkedin, resume]` and framework `data-react-helmet` produces a stable signature regardless of which company subdomain it lives under.

## Detection of known ATSes

Before drafting a new adapter, `learn.py` compares the signature against the bundled adapter signatures. If it matches one of {Greenhouse, Lever, Workday, Gupy, SmartRecruiters, Ashby, Recruitee, BambooHR, Personio, Jobvite}, we copy that adapter and mark it `inherited_from: <name>`.

Hashes for the known platforms are pre-computed and stored in `assets/known_ats_signatures.json` (phase 4 deliverable).

## Drafting a new adapter

If novel:

1. Take a screenshot to `runs/<iso>/learn_<sig>.png`.
2. Dump the form DOM (with input *values* stripped — only attributes) to `runs/<iso>/learn_<sig>.html`.
3. For each input, lookup its `name`, `placeholder`, `aria-label`, and surrounding `<label>` text against `assets/field_labels.yaml` (the BR/EN label dictionary). Best match wins, threshold 0.8 token overlap.
4. Emit a YAML adapter to `$XDG_DATA_HOME/job-hunter/adapters_inbox/<sig>.yaml` with our best guesses for `source:` (e.g. `secret.cpf`, `profile.email`, `file.resume_pt`).
5. Mark the application's last `fill_attempt` as `aborted_for_review`, surface in `job review`.

## Promotion

After human review:

```
job adapter promote <sig>
```

Moves `adapters_inbox/<sig>.yaml` -> `adapters_user/<sig>.yaml`, registers in the `site_adapters` table with `success_count=0`, `auto_eligible=false`.

## Reliability tracking

Every fill attempt increments `success_count` or `failure_count` for the adapter used. Auto mode requires `success / (success+failure) >= 0.9`.

After **3 consecutive** failures (regardless of overall rate), the adapter is marked `paused_for_review: true` in the DB. Surface in `job review` until a human re-promotes.

## Label dictionary improvement

When a human edits a drafted adapter to swap field bindings (e.g. `source: secret.phone` -> `source: secret.cell_phone`), the diff is appended to `$XDG_CONFIG_HOME/job-hunter/field_labels.yaml` so future drafts pick up the correction.

`job adapter contribute <sig>` packages the merged adapter + label additions into a branch on this repo (or `$JOB_HUNTER_UPSTREAM_REPO`) and opens a PR via `gh`. Requires `gh auth status` clean; otherwise prints the manual diff and command.
