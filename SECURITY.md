# Security Policy

## Supported Versions

| Version | Supported |
| ------- | --------- |
| 1.3.x   | Yes       |
| 1.1.x   | Yes       |
| < 1.1   | No        |

1.2.0 was never published to PyPI.

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Report privately via GitHub Security Advisories:
https://github.com/yawway365/draftedi-core/security/advisories/new

## Response Timeline

| Severity | Acknowledgment | Patch Target |
| -------- | -------------- | ------------ |
| High / Critical | 72 hours | 30 days |
| Medium | 72 hours | 60 days |
| Low | 72 hours | Next minor release |

## What to Include

A useful report contains:

- Description of the vulnerability and its potential impact
- Steps to reproduce (minimal code sample preferred)
- Python version (`python --version`)
- draftedi version (`pip show draftedi`)
- Any relevant EDI file snippets (redact PII/PHI before sending)

## Scope

draftedi-core ships with **zero runtime dependencies**. The attack surface is
limited to EDI parsing and validation logic. Reports in scope include:

- Malformed input that causes a crash, hang, or uncontrolled resource use
- Logic errors that produce incorrect validation results on security-relevant
  segments (e.g., ISA, GS, ST envelopes)
- Path traversal or arbitrary file access. The parser does not open files; the
  only code that reads files is `JSONSkeletonSpecProvider`, which builds file
  names from GS08 and ST01 of the document being validated. In 1.3.0 crafted
  values could make it read `.json` files outside the spec directory; this is
  fixed in 1.3.1.

Out of scope: vulnerabilities in Python itself, the operating system, or
developer-only tooling not shipped with the library.

## Disclosure Policy

Once a fix is released, a GitHub Security Advisory will be published. Reporters
are credited by name or handle unless they prefer anonymity.
