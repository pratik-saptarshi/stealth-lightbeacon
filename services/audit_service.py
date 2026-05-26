"""Reusable audit orchestration service."""

from __future__ import annotations

import inspect
import logging
import asyncio
from dataclasses import replace
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx

import config
from crawler import Crawler
from modules.base import BaseEvaluator, EvaluationResult, Issue
from modules.renderer import PlaywrightRenderer
from report.formats import build_report_payload
from services.errors import AuditServiceError
from utils.ssrf_guard import SSRFGuard, SSRFHTTPTransport, SSRFViolationError


LOGGER = logging.getLogger(__name__)


def _resolve_renderer(render: bool, scraping_engine: Optional[Any]) -> Optional[Any]:
    if scraping_engine is not None:
        return scraping_engine
    if render:
        return PlaywrightRenderer()
    return None


async def _collect_pages(
    url: str,
    client: httpx.AsyncClient,
    renderer: Optional[Any],
    allow_private: bool,
    crawl_depth: int,
    max_urls: int,
    check_links: bool,
) -> tuple[Dict[str, str], Optional[Crawler]]:
    crawled_pages: Dict[str, str] = {}
    crawler = None
    if crawl_depth > 0 or check_links:
        crawler = Crawler(
            url,
            max_depth=crawl_depth if crawl_depth > 0 else 1,
            max_urls=max_urls,
            allow_private=allow_private,
        )
        crawled_pages = await crawler.crawl(client, renderer)

        if crawl_depth == 0 and check_links:
            start_normalized = crawler.start_url
            matching_url = next(
                (
                    page_url
                    for page_url in crawled_pages
                    if urlparse(page_url).path == urlparse(start_normalized).path
                ),
                start_normalized,
            )
            crawled_pages = {matching_url: crawled_pages.get(matching_url, "")}
        return crawled_pages, crawler

    try:
        if renderer:
            if hasattr(renderer, "scrape"):
                html_content = await renderer.scrape(url)
            else:
                html_content = await renderer.render(url)
            crawled_pages[url] = html_content
        else:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
            crawled_pages[str(response.url)] = response.text
    except Exception as exc:  # pragma: no cover - error path covered in service tests
        raise AuditServiceError(
            title=f"Error: Failed to fetch target URL: {url}",
            detail=str(exc),
            exit_code=1,
        ) from exc

    return crawled_pages, None


async def _evaluate_pages(
    crawled_pages: Dict[str, str],
    active_modules: List[BaseEvaluator],
    client: httpx.AsyncClient,
    allow_private: bool,
    check_api: bool,
    store: Optional[Any],
    run_id: Optional[str],
) -> Dict[str, List[EvaluationResult]]:
    all_eval_results: Dict[str, List[EvaluationResult]] = {
        mod.domain: [] for mod in active_modules
    }

    for page_url, html_content in crawled_pages.items():
        if store and run_id:
            await store.record_page(run_id, page_url, html_content)

        tasks = []
        for module in active_modules:
            kwargs = {"allow_private": allow_private}
            if type(module).__name__ == "DrupalEvaluator":
                kwargs["check_api"] = check_api
            tasks.append(module.evaluate(html_content, page_url, client, **kwargs))

        page_results = await asyncio.gather(*tasks, return_exceptions=True)

        for idx, result in enumerate(page_results):
            mod = active_modules[idx]
            if isinstance(result, Exception):
                LOGGER.warning(
                    "Evaluator '%s' failed on %s: %s",
                    mod.domain,
                    page_url,
                    result,
                )
                continue

            url_path = urlparse(page_url).path or "/"
            updated_issues = []
            for issue in result.issues:
                updated_issues.append(
                    replace(issue, location=f"[{url_path}] {issue.location}")
                )
                if store and run_id:
                    await store.record_finding(
                        run_id=run_id,
                        page_url=page_url,
                        domain_id=mod.domain,
                        issue_id=issue.id,
                        severity=issue.severity,
                        message=issue.message,
                        location=issue.location,
                        remedy=issue.remedy,
                    )
            updated_result = replace(result, issues=tuple(updated_issues))
            all_eval_results[mod.domain].append(updated_result)

    return all_eval_results


def _consolidate_results(
    url: str,
    active_modules: List[BaseEvaluator],
    all_eval_results: Dict[str, List[EvaluationResult]],
    crawler: Optional[Crawler],
    check_links: bool,
) -> List[EvaluationResult]:
    consolidated_results: List[EvaluationResult] = []

    for mod in active_modules:
        domain_results = all_eval_results.get(mod.domain, [])
        if not domain_results:
            continue

        avg_score = sum(result.score for result in domain_results) / len(domain_results)
        all_issues: list[Issue] = []
        for result in domain_results:
            all_issues.extend(result.issues)

        if (
            mod.domain == "Technical SEO"
            and check_links
            and crawler
            and hasattr(crawler, "broken_links")
            and crawler.broken_links
        ):
            for broken_link, status in crawler.broken_links.items():
                all_issues.append(
                    Issue(
                        id="R-SEO-BROKEN-LINK",
                        severity=config.SEVERITY_WARNING,
                        message=(
                            "Discovered broken outbound link: "
                            f"{broken_link} returned status {status}."
                        ),
                        location="Link href reference",
                        remedy=(
                            "Inspect and correct the destination URL or remove "
                            "the inactive hyperlink reference."
                        ),
                    )
                )

        merged_metadata = {"crawled_pages_count": len(domain_results)}
        for result in domain_results:
            for key, value in result.metadata.items():
                if key not in merged_metadata:
                    merged_metadata[key] = value
                elif isinstance(value, (int, float)):
                    merged_metadata[key] += value

        consolidated_results.append(
            EvaluationResult(
                domain=mod.domain,
                score=round(avg_score, 1),
                issues=tuple(all_issues),
                metadata=merged_metadata,
            )
        )

    return consolidated_results


async def run_evaluation(
    url: str,
    active_modules: List[BaseEvaluator],
    allow_private: bool = False,
    crawl_depth: int = 0,
    max_urls: int = 10,
    render: bool = False,
    http2: bool = False,
    scraping_engine: Optional[Any] = None,
    check_links: bool = False,
    check_api: bool = False,
    store: Optional[Any] = None,
    run_id: Optional[str] = None,
    auth_token: Optional[str] = None,
) -> List[EvaluationResult]:
    try:
        guard = SSRFGuard(allow_private=allow_private)
        await guard.validate(url)
    except SSRFViolationError as exc:
        raise AuditServiceError(
            title=f"Security Error: SSRF Protection blocked request to {url}",
            detail=str(exc),
            exit_code=1,
        ) from exc

    renderer = _resolve_renderer(render=render, scraping_engine=scraping_engine)
    guard = SSRFGuard(allow_private=allow_private)
    transport = SSRFHTTPTransport(guard=guard, http2=http2)
    client = httpx.AsyncClient(
        transport=transport,
        timeout=config.REQUEST_TIMEOUT,
        headers=config.build_request_headers(auth_token),
    )

    try:
        crawled_pages, crawler = await _collect_pages(
            url=url,
            client=client,
            renderer=renderer,
            allow_private=allow_private,
            crawl_depth=crawl_depth,
            max_urls=max_urls,
            check_links=check_links,
        )
        all_eval_results = await _evaluate_pages(
            crawled_pages=crawled_pages,
            active_modules=active_modules,
            client=client,
            allow_private=allow_private,
            check_api=check_api,
            store=store,
            run_id=run_id,
        )
        consolidated_results = _consolidate_results(
            url=url,
            active_modules=active_modules,
            all_eval_results=all_eval_results,
            crawler=crawler,
            check_links=check_links,
        )

        if store and run_id:
            report_payload = build_report_payload(url, consolidated_results)
            await store.finish_run(
                run_id,
                report_payload,
                len(crawled_pages),
                len(consolidated_results),
            )
    finally:
        close_result = client.aclose()
        if inspect.isawaitable(close_result):
            await close_result
        from utils.browser_pool import BrowserPool

        await BrowserPool.get_instance().close()

    return consolidated_results
