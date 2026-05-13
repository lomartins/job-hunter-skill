# Adapter: Lever

`platform_signature: lever`. Hosted at `jobs.lever.co/<company>/<job-id>/apply`.

## Match

```yaml
match:
  url_pattern: "jobs.lever.co/*/apply"
  dom_markers:
    - "form[name='application']"
```

## Field map

| Input | Source |
|-------|--------|
| `input[name='name']` | `profile.full_name` |
| `input[name='email']` | `profile.email` |
| `input[name='phone']` | `secret.JOB_HUNTER_PHONE` |
| `input[name='org']` | `profile.current_company` (optional) |
| `input[name='urls[LinkedIn]']` | `profile.links.linkedin` |
| `input[name='urls[GitHub]']` | `profile.links.github` |
| `input[name='resume']` (file) | `file.resume_en` |
| Custom card-question inputs | learned |

## Phase 1 scope

Spec stub. YAML lands in **Phase 4**.
