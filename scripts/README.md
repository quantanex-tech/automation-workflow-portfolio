# Scripts

## `sanitise_n8n_export.py`

Creates a conservative first-pass copy of an n8n workflow export.

```bash
python scripts/sanitise_n8n_export.py \
  raw/workflow.raw.json \
  case-studies/example/workflow/workflow.sanitised.json \
  --name "Portfolio example"
```

The script removes common n8n metadata, credential references, pinned data, webhook identifiers and obvious personal or secret patterns.

## `audit_portfolio.py`

Scans the repository for common sensitive patterns before publishing.

```bash
python scripts/audit_portfolio.py .
```

Both scripts are only safety aids. They cannot recognise every client name, prompt, product identifier or commercially sensitive business rule. Manually inspect the complete export, screenshots and Git history before making the repository public.
