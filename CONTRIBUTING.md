# Contributing Guidelines

Thank you for your interest in contributing to this repository! To ensure a healthy, professional, and maintainable codebase, we request all contributors follow these guidelines.

---

## Code Style & Formatting

We maintain a clean and standard Python format governed by **Ruff** (PEP 8 rules).

- Follow standard naming patterns (e.g. `snake_case` for variables and functions, `CamelCase` for classes).
- Keep import lists organized and clean.
- Ensure all source modifications pass formatting verification before submission.

---

## Test-Driven Development (TDD) Lifecycle

We enforce strict quality boundaries using **Red-Green-Refactor** TDD principles:

1. **Write failing tests first:** Always build unit or integration test stubs defining expected behavior before modifying implementation logic.
2. **Implement minimum logic:** Write clean code specifically designed to make the new tests succeed.
3. **Refactor and verify:** Optimize the structural elements while verifying the entire test suite stays green.

Execute the test suites regularly during development:
```bash
# Run all unit/integration tests
pytest -v
```

---

## Pull Request Guidelines

1. Fork the repository and build feature additions in a dedicated topic branch.
2. Verify that unit tests successfully pass with a minimum **90% branch coverage** target.
3. Squash commits into structured, human-readable logical groups.
4. Open a Pull Request targetting the `main`/`master` branch, describing changes and link to related issues clearly.

## Dependency Validation

We validate pinned dependencies against live package indices before merge.

```bash
pre-commit install
pre-commit run dependency-validation --all-files
```
