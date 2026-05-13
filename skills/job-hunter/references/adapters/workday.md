# Adapter: Workday

`platform_signature: workday`. Most complex of the bundled adapters. Multi-step wizard, lots of conditional inputs.

## Match

```yaml
match:
  url_pattern: "*.myworkdayjobs.com/*"
  dom_markers:
    - "[data-automation-id='applyManually']"
```

## Strategy

Workday is paginated across multiple wizard steps:
1. Account creation / sign-in (we use the "apply manually" path, no account)
2. My Information
3. My Experience (resume upload + parsed sections)
4. Application Questions
5. Voluntary Disclosures
6. Self-Identify
7. Review + Submit

The adapter declares one section per step with `step:` markers; `apply.py` advances by clicking the "Continue" button after each step's fields are filled.

## Field map (sketch)

| Step | Input (data-automation-id) | Source |
|------|---------------------------|--------|
| my-info | `firstName` | `profile.first_name` |
| my-info | `lastName` | `profile.last_name` |
| my-info | `email` | `profile.email` |
| my-info | `phone-deviceType` (select) | constant "Mobile" |
| my-info | `phone-number` | `secret.JOB_HUNTER_PHONE` |
| my-experience | `file-upload-input-ref` | `file.resume_en` |
| ... | ... | ... |

## Auto-eligibility

Off by default. Workday's wizard is fragile; require many clean shadow submits before flipping.

## Phase 1 scope

Spec stub. YAML lands in **Phase 4** (lowest priority among bundled adapters — most likely to need iteration).
