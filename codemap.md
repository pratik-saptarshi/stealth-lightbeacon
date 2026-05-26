# Repository Atlas: stealth-lightbeacon

## Project Responsibility
Asynchronous diagnostic audit engine for Drupal/PHP sites. The repository
combines a Typer CLI, async crawler, pluggable evaluation modules, report
renderers, and release/docs contracts for CI and human operators.

## System Entry Points
- `main.py`: CLI entry point and orchestration pipeline.
- `crawler.py`: recursive async crawler and link-discovery engine.
- `config.py`: shared runtime constants, headers, and environment loading.
- `report/formats.py`: canonical normalized payload and renderer layer.
- `report/generator.py`: HTML report generator.
- `utils/agent_card.py`: orchestration manifest for downstream automation.
- `docs/architecture.md`: canonical architecture guide.
- `docs/architecture-beads-plan.md`: phase-based remediation backlog.

## Repository Directory Map
| Directory | Responsibility Summary | Detailed Map |
|---|---|---|
| `modules/` | Shared evaluator layer, DOM adapters, and domain checks for SEO, accessibility, performance, UX, Drupal, and AEO/GEO. | [View Map](modules/codemap.md) |
| `modules/scraping/` | Pluggable acquisition strategies with SSRF-aware fallback behavior. | [View Map](modules/scraping/codemap.md) |
| `report/` | Normalized report payload and rendering pipeline for JSON, markdown, XML, and HTML output. | [View Map](report/codemap.md) |
| `utils/` | Shared infrastructure for vectorization, storage, SSRF protection, browser reuse, diffing, recon, budgets, and BOM maintenance. | [View Map](utils/codemap.md) |
| `ci-recipes/` | Provider-specific CI recipes for running the audit pipeline in GitHub Actions, Bitbucket, and GitLab. | [View Map](ci-recipes/codemap.md) |

## Design
The codebase follows a layered architecture: CLI orchestration at the root,
strategy-based scraping underneath, evaluator modules over normalized HTML, and
report/persistence helpers that all consume the same payload contract.

## Flow
CLI input flows through `main.py` into SSRF validation, crawl/render acquisition,
parallel evaluator execution, payload normalization, report generation, and
optional persistence/search indexing.

## Integration
Root docs and alias files are part of the release contract. Submaps are the
authoritative detail sources for directory-specific behavior.
