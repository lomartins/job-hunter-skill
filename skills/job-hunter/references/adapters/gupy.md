# Adapter: Gupy

`platform_signature: gupy` (special — set by string match on hostname pattern, not the structural hash, because every Gupy form has slight markup differences per tenant).

## Match

```yaml
match:
  url_pattern: "*.gupy.io/jobs/*"
  dom_markers:
    - "div[data-testid='application-form']"
```

## Field map (typical)

| Page input | Adapter source | Required |
|------------|----------------|----------|
| `input[name='name']` | `profile.full_name` (resolved from `secret.JOB_HUNTER_FULL_NAME` because it's PII) | yes |
| `input[name='email']` | `profile.email` (from profile.yaml `links.email`) | yes |
| `input[name='phone']` | `secret.JOB_HUNTER_PHONE` | yes |
| `input[name='cpf']` | `secret.JOB_HUNTER_CPF` with mask `###.###.###-##` | yes |
| `input[name='linkedin']` | `profile.links.linkedin` | optional |
| `input[type='file'][name='resume']` | `file.resume_pt` | yes |
| `textarea[name='cover_letter']` | `generate.cover_letter` | optional |

## Submit

```yaml
submit:
  selector: "button[type='submit']"
  mode: shadow
  auto_eligible: false
  pre_submit_checks:
    - screenshot
    - assert_no_pii_in_logs
    - assert_all_required_filled
    - assert_resume_matches_locale
  cooldown_seconds: 30
```

## Quirks

- Some Gupy tenants add custom screening questions (radio groups) below the standard form. If `learn.py` detects unmapped required inputs, it appends them to the inbox draft with `source: TODO`. Promote only after editing.
- Resume upload sometimes needs a 1-2s wait after click before the file dialog accepts the path. We use Playwright's `set_input_files` which bypasses the dialog.

## Phase 1 scope

Spec stub. YAML lands in **Phase 4** at `assets/adapters/gupy.yaml`.
