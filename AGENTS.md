# Project guidance

## Scope
- This project contains small Python scripts for authenticated SGP access and financial-report extraction.
- Keep changes focused on the requested behavior and preserve the scripts' existing Portuguese prompts and messages.

## Authentication and data handling
- Keep using the same `requests.Session` for login and subsequent requests so authentication cookies are preserved.
- Never hard-code, log, or commit SGP usernames, passwords, session cookies, contract identifiers, or real financial data.
- Treat saved response files as sensitive personal and financial data. Do not add them to source control or expose their contents in logs.
- Make requests only for accounts and records the user is authorized to access; keep TLS verification enabled.

## Dependencies and validation
- The scripts currently use `requests` and `beautifulsoup4`; avoid adding dependencies for standard-library tasks.
- There is no test or dependency configuration in the repository yet. For Python changes, run a syntax check such as `python -m py_compile login.py ficha_financeira.py`.
- Do not run live login or report requests as a validation step; those require credentials and access to the external SGP service.