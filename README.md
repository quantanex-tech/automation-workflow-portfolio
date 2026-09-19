# Paul Hopgood - automation workflow portfolio

This repository contains selected case studies from automation, API integration, AI-agent evaluation and business-system projects that I designed, built and tested.

The examples focus on how the systems work, the decisions behind them and how they handle real operational problems. Client data, credentials, internal identifiers and commercially sensitive details have been removed. Some exported workflows may also use synthetic names or simplified logic where the original implementation cannot be shared safely.

## Case studies

| Case study | What it demonstrates | Status represented here |
|---|---|---|
| [Order tracking and fulfilment reconciliation](case-studies/01-order-tracking-and-fulfilment/README.md) | Complex n8n orchestration, Shopify integration, file processing, JavaScript, matching logic and exception handling | Sanitised production case study |
| [WhatsApp AI assistant with tools and memory](case-studies/02-whatsapp-ai-assistant/README.md) | Evolution API, webhooks, LLM tool use, Postgres memory, Gmail, calendar and task integrations | Working AI Assistant case study |
| [Voice agent appointment booking](case-studies/03-voice-agent-appointment-booking/README.md) | Voice APIs, asynchronous callbacks, structured results, calendar booking and failure paths | Voice caller case study |
| [AI email classification and triage](case-studies/04-ai-email-categorisation/README.md) | Outlook automation, LLM classification, batching, retries, validation and operational reporting | Sanitised operational case study |
| [Evaluating a local LLM for reliable agent tool use](case-studies/05-local-llm-agent-evaluation/README.md) | Native tool calling, repeatable model evaluation, long-chain reliability and externally verified coding tasks | Controlled local-model evaluation |

## What the portfolio demonstrates

- Production n8n workflow design and support
- REST APIs, webhooks, OAuth and JSON data handling
- JavaScript Code nodes and targeted scripting
- SQL-backed validation and reporting
- LLM classification, extraction, agents and tool calling
- Repeatable AI-agent evaluation, failure classification and external verification
- Shopify, Microsoft 365, Google Workspace and communications integrations
- Retries, duplicate controls, failure routes, logging and manual review points
- Process discovery, testing, documentation and operational handover

## Authorship and use of AI coding tools

I designed and built the four featured automation workflows from scratch. For the model-evaluation case study, I designed the methodology, scenarios, scoring rules and acceptance decision, and built and ran the evaluation harnesses. I used AI coding tools to help draft or troubleshoot selected JavaScript and Python. I reviewed, tested and adapted that code before using it.

Template-derived experiments are not presented as original case studies.

## How each case study is presented

Each folder contains, where relevant:

- A short overview for a recruiter or hiring manager
- The problem and constraints
- A simplified architecture diagram
- The important implementation decisions
- Reliability, error handling and edge cases
- The result and what I personally built
- Screenshots, compact evaluation evidence or other supporting artifacts
- A sanitised workflow export or reusable script when sharing it is safe and useful

The written case study is the main artifact. Raw exports and run archives on their own are difficult to assess and can expose more information than expected.

## Safety and confidentiality

Published workflow exports, scripts, screenshots and evaluation summaries are sanitised. Raw production exports and complete model-run archives are not stored in this repository. Client data, credentials, private network details, absolute local paths and operational identifiers are removed.
