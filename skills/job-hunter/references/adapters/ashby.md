# Adapter: Ashby

`platform_signature: ashby`. Hosted at `jobs.ashbyhq.com/<company>` or custom domains using Ashby's iframe.

## Match

```yaml
match:
  url_pattern: "jobs.ashbyhq.com/*"
  dom_markers:
    - "form[data-form='application']"
```

## Field map

| Input | Source |
|-------|--------|
| `input[name='_systemfield_name']` | `profile.full_name` |
| `input[name='_systemfield_email']` | `profile.email` |
| `input[name='_systemfield_phoneNumber']` | `secret.JOB_HUNTER_PHONE` |
| `input[name='_systemfield_resume']` (file) | `file.resume_en` |
| `input[name='_systemfield_linkedinUrl']` | `profile.links.linkedin` |
| `input[name='_systemfield_githubUrl']` | `profile.links.github` |
| Custom-field inputs | learned |

## Phase 1 scope

Spec stub. YAML lands in **Phase 4**.
