# Contributing to Omni-Agent

Thank you for your interest in contributing! This document provides guidelines for both human and AI contributors.

## How to Contribute

1. **Fork** the repository and create a feature branch.
2. **Implement** your changes following the code style below.
3. **Write tests** for any new functionality.
4. **Submit a Pull Request** with a clear description.

## Code Style

- Follow [PEP 8](https://peps.python.org/pep-0008/) for Python code.
- Add docstrings to all public classes and methods.
- Keep functions focused and small.

## Environment files

Only commit template env files such as `.env.example`. Never commit real `.env` or `.env.*` files that may contain secrets.

When you introduce a new environment variable, you must document it in `.env.example` (and in `README.md` if it affects setup).

If you add a new committed env template (like `.env.local.example`), also add it to the allowlist in `.gitignore` so it is tracked.

## Branching Strategy

- `main` – stable, production-ready code.
- `feature/<name>` – new features.
- `fix/<name>` – bug fixes.

## Reporting Bugs

Open a GitHub issue with the label `bug` and include:
- Steps to reproduce
- Expected vs actual behaviour
- Relevant logs or screenshots

## Requesting Features

Open a GitHub issue with the label `feature` and describe:
- The problem being solved
- The proposed solution
- Any alternatives considered

## Code of Conduct

Be respectful and constructive. All contributors are expected to abide by the [Contributor Covenant](https://www.contributor-covenant.org/).
