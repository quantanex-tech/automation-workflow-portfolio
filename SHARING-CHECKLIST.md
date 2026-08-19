# Publishing checklist

- [ ] The repository is still private while content is being prepared.
- [ ] Every case study states whether it is production work, an operational workflow, a prototype or a demo.
- [ ] Every case study states what Paul personally designed and built.
- [ ] Template-derived work is either excluded or attributed clearly.
- [ ] All screenshots use synthetic or anonymised data.
- [ ] Browser chrome, hostnames, avatars and bookmarks are cropped out.
- [ ] Credential selectors and account names are not visible.
- [ ] Raw workflow exports are outside the repository.
- [ ] Sanitised workflow exports contain no `credentials`, `pinData`, `webhookId`, owner or sharing metadata.
- [ ] Client names, emails, phone numbers, order numbers and document IDs are removed.
- [ ] Prompts and Code nodes have been checked manually for confidential information.
- [ ] `python scripts/audit_portfolio.py .` reports no findings.
- [ ] Git history contains no earlier version of a secret or client data.
- [ ] Relative links and Mermaid diagrams render correctly on GitHub.
- [ ] The root README gives a recruiter a useful overview in under two minutes.
- [ ] The portfolio URL has been added to the CV and LinkedIn profile.
