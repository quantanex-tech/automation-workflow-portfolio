# Paul Hopgood - automation workflow portfolio

This repository contains selected case studies from n8n, API integration, AI-assisted automation and business-system projects that I designed and built.

The examples focus on how the systems work, the decisions behind them and how they handle real operational problems. Client data, credentials, internal identifiers and commercially sensitive details have been removed. Some exported workflows may also use synthetic names or simplified logic where the original implementation cannot be shared safely.

## Case studies

| Case study | What it demonstrates | Status represented here |
|---|---|---|
| [Order tracking and fulfilment reconciliation](case-studies/01-order-tracking-and-fulfilment/README.md) | Complex n8n orchestration, Shopify integration, file processing, JavaScript, matching logic and exception handling | Sanitised production case study |
| [WhatsApp AI assistant with tools and memory](case-studies/02-whatsapp-ai-assistant/README.md) | Evolution API, webhooks, LLM tool use, Postgres memory, Gmail, calendar and task integrations | Working prototype case study |
| [Voice agent appointment booking](case-studies/03-voice-agent-appointment-booking/README.md) | Voice APIs, asynchronous callbacks, structured results, calendar booking and failure paths | Technical demo case study |
| [AI email classification and triage](case-studies/04-ai-email-classification/README.md) | Outlook automation, LLM classification, batching, retries, validation and operational reporting | Sanitised operational case study |

## What the portfolio demonstrates

- Production n8n workflow design and support
- REST APIs, webhooks, OAuth and JSON data handling
- JavaScript Code nodes and targeted scripting
- SQL-backed validation and reporting
- LLM classification, extraction, agents and tool calling
- Shopify, Microsoft 365, Google Workspace and communications integrations
- Retries, duplicate controls, failure routes, logging and manual review points
- Process discovery, testing, documentation and operational handover

## Authorship and use of AI coding tools

I designed and built the four featured workflows from scratch. I used AI coding tools to help draft or troubleshoot some JavaScript used in Code nodes. I reviewed, tested and adapted that code before using it in the workflow.

Template-derived experiments are not presented as original case studies. For example, a separate WhatsApp RAG experiment began from a template and is intentionally excluded from this portfolio.

## How each case study is presented

Each folder contains:

- A short overview for a recruiter or hiring manager
- The business problem and constraints
- A simplified architecture diagram
- The important implementation decisions
- Reliability, error handling and edge cases
- The result and what I personally built
- Guidance for screenshots and supporting evidence
- A location for a sanitised n8n export, when sharing the export is safe and useful

The written case study is the main artifact. A raw workflow export on its own is difficult to assess and can expose more information than expected.

## Safety and confidentiality

Raw n8n exports are not stored in this repository. Before adding an export, use the first-pass sanitisation script and then inspect the result manually:

```bash
python scripts/sanitise_n8n_export.py \
  path/to/raw-export.json \
  case-studies/01-order-tracking-and-fulfilment/workflow/workflow.sanitised.json

python scripts/audit_portfolio.py .
```

The scripts cannot understand every piece of client or business context. A clean automated audit is not a substitute for manual review.

## Usage

This is a portfolio repository. No licence is granted to copy, deploy or reuse the workflows or supporting materials.
