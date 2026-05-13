# Template skill

Copy this directory to `skills/<your-skill-name>/`, edit `SKILL.md`, register in `.claude-plugin/marketplace.json`:

```json
{
  "plugins": [
    { "name": "your-skill-name", "source": "./skills/your-skill-name", "version": "0.1.0", ... }
  ]
}
```

Bump the marketplace `name` if you want a separate marketplace, or add as another plugin entry. CI's version-bump check works per-plugin.
