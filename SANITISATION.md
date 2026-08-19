# Sanitisation guide

n8n exports can reveal sensitive information even when they do not contain passwords or API tokens. Treat every raw export as confidential until it has been reviewed.

## Remove or replace

- Credential objects, credential IDs and account names
- Webhook IDs and webhook paths
- Pinned execution data
- Workflow owner, project and sharing metadata
- Email addresses, phone numbers and names
- Private IP addresses, hostnames and internal URLs
- Google document, calendar, spreadsheet and folder identifiers
- Client names, supplier names and internal project names
- API keys, bearer tokens, secrets and signed URLs
- Real order numbers, SKUs, invoices and customer details
- Prompts that contain confidential process rules or client information
- Code comments that refer to internal systems or people
- Cached result names and URLs stored by n8n resource selectors

## Screenshots

Screenshots are often riskier than the JSON export because the n8n data pane can show complete payloads.

Before adding a screenshot:

1. Collapse the execution data pane.
2. Use synthetic test data.
3. Check every node name, sticky note and credential selector.
4. Hide browser bookmarks, tabs, hostnames and account avatars.
5. Crop the image to the relevant part of the canvas.
6. Open the exported PNG at full resolution and inspect it again.

## Export workflow

1. Export the workflow to a local `raw/` directory. The repository ignores this directory.
2. Run `scripts/sanitise_n8n_export.py` to create a first-pass copy.
3. Compare the raw and sanitised versions locally.
4. Search the sanitised JSON for client names, URLs, IDs and real data values.
5. Import the sanitised workflow into a disposable n8n instance if you need to check that the diagram still makes sense.
6. Add the sanitised file only when it is safe to publish.
7. Run `scripts/audit_portfolio.py .` before committing.

## Important limitation

Automated redaction works on patterns. It will not recognise that an ordinary-looking product name, prompt, spreadsheet title or JavaScript constant is commercially sensitive. Manual review remains required.
