# Security Policy

We take security vulnerabilities seriously. We request that security researchers, developers, and users report potential vulnerabilities responsibly following the guidelines below.

---

## Reporting a Vulnerability

**Please do NOT open a public GitHub issue for security vulnerabilities.**

If you discover a security flaw (such as an SSRF bypass, Stored XSS, or private data leak risk), please report it privately:
- Use GitHub's private vulnerability reporting for this repository once it is published.
- If private reporting is unavailable, contact the maintainers through the same
  private release channel used for coordination before sharing details publicly.
- Include comprehensive details: target systems, step-by-step reproduction instructions, payload evidence, and potential impact assessments.

---

## In Scope

Reports are in scope when they affect:

- SSRF bypasses or private-range access controls.
- Stored or reflected XSS in rendered reports or crawler output.
- Private data exposure in persisted reports, artifacts, or logs.
- Authentication, authorization, or secret-handling failures.
- Supply-chain or dependency issues that can affect release integrity.

---

## Security Response SLA

Upon receiving a private security report:
- **Acknowledgement:** We will acknowledge receipt of the vulnerability within **48 hours**.
- **Investigation:** We will evaluate the impact and formulate mitigation patches within **7 days**.
- **Resolution & Release:** We will coordinate patch releases and, if appropriate, public CVE disclosure under a standard responsible disclosure timeframe (typically within 30 to 90 days depending on complexity).
