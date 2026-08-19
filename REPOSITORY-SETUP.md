# Repository setup

## Recommended GitHub settings

Repository name: `automation-workflow-portfolio`

Description:

> Sanitised case studies of n8n, API, AI and business-system automations designed and built by Paul Hopgood.

Start the repository as **private**. Make it public only after every export and screenshot has passed the sanitisation checks.

Suggested topics:

- `n8n`
- `workflow-automation`
- `api-integration`
- `ai-agents`
- `javascript`
- `webhooks`
- `ecommerce-automation`
- `low-code`

## Create and push the repository

Create an empty private repository on GitHub, without adding a README or licence. Then run:

```bash
cd automation-workflow-portfolio
git init
git branch -M main
git add .
git commit -m "Create automation portfolio structure"
git remote add origin https://github.com/Quantanex-Tech-ltd/automation-workflow-portfolio.git
git push -u origin main
```

Replace the remote URL if the repository will live under a personal GitHub account instead of the Quantanex organisation.

## Before making it public

1. Add screenshots that use synthetic or redacted data.
2. Add only sanitised workflow exports.
3. Run `python scripts/audit_portfolio.py .`.
4. Open every image at full size and inspect it manually.
5. Review the Git history. A secret removed in a later commit still exists in earlier commits.
6. Make the repository public only when the audit reports no findings and the manual review is complete.

If sensitive content is committed accidentally, delete the repository or rewrite its history before publishing. A normal follow-up commit is not enough.
