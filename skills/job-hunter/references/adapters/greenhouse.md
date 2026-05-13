# Adapter: Greenhouse

`platform_signature: greenhouse`. Match via DOM marker — Greenhouse forms have `#application_form` and an iframe pattern at `boards.greenhouse.io`.

## Match

```yaml
match:
  url_pattern: "boards.greenhouse.io/*"
  dom_markers:
    - "form#application_form"
```

## Field map (typical)

| Input | Adapter source |
|-------|---------------|
| `#first_name` | `profile.first_name` |
| `#last_name` | `profile.last_name` |
| `#email` | `profile.email` |
| `#phone` | `secret.JOB_HUNTER_PHONE` |
| `#resume` (file) | `file.resume_en` (most Greenhouse boards are international) |
| `#cover_letter` (file) | `file.cover_letter_en` |
| Custom question inputs | learned per board |

## Submit

```yaml
submit:
  selector: "#submit_app"
  mode: shadow
  auto_eligible: false
```

## Phase 1 scope

Spec stub. YAML lands in **Phase 4**.
