"""Default field generators.

PII isolation: generators receive only PUBLIC context — no env vars, no
profile secrets. The shipped `cover_letter` generator returns a deterministic
templated paragraph. Users replace it via the `generate_cover_letter` pluggy
hook (Phase 6+).
"""

from __future__ import annotations

from collections.abc import Callable

GeneratorFn = Callable[[dict[str, str]], str]


def cover_letter(ctx: dict[str, str]) -> str:
    """Generate a short templated cover letter.

    Public context only — `job_title`, `company`, `role_summary`,
    `public_profile_blurb`. No PII. Same inputs → same output (deterministic).
    """
    job_title = ctx.get("job_title", "the role")
    company = ctx.get("company", "your team")
    role_summary = (ctx.get("role_summary") or "").strip()
    blurb = (ctx.get("public_profile_blurb") or "").strip()

    body_lines = [
        f"Dear {company} hiring team,",
        "",
        f"I'm writing to express my interest in the {job_title} role.",
    ]
    if role_summary:
        body_lines.append(f"What drew me to this opportunity in particular: {role_summary}")
    if blurb:
        body_lines.append("")
        body_lines.append(blurb)
    body_lines.append("")
    body_lines.append(
        "I'd be glad to discuss how my experience aligns with what your team needs. "
        "Thanks for your time."
    )
    body_lines.append("")
    return "\n".join(body_lines)


DEFAULTS: dict[str, GeneratorFn] = {
    "cover_letter": cover_letter,
}
