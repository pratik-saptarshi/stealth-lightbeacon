"""
main.py — Main orchestration and Typer CLI entry point for Stealth Lightbeacon.
"""

import asyncio
import inspect
import os
import json
import httpx
import typer
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, replace
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

# Import configuration and constants
import config
from modules.base import BaseEvaluator, EvaluationResult, Issue
from report.formats import build_report_payload, render_report_format

# Initialize Typer and Rich Console
try:
    import rich_click as click
    click.rich_click.USE_RICH_MARKUP = True
    click.rich_click.SHOW_ARGUMENTS = True
    click.rich_click.GROUP_ARGUMENTS_OPTIONS = True
    # Patch Click's formatting with rich-click
    typer.main.click = click
except ImportError:
    pass

app = typer.Typer(help="Stealth Lightbeacon: Diagnostic Audit Tool for SEO, Performance, and Accessibility.")
console = Console()


@dataclass(frozen=True)
class RuntimeSettings:
    url: Optional[str]
    output_dir: str
    audits: List[str]
    auth_token: str
    fail_on_critical: bool


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def build_runtime_settings(
    url: Optional[str],
    audits: Optional[str],
    fail_on_critical: bool,
    output_dir: Optional[str] = None,
    auth_token: Optional[str] = None,
) -> RuntimeSettings:
    resolved_url = (url or os.getenv("SLB_TARGET_URL", "")).strip() or None
    resolved_audits = (audits or os.getenv("SLB_AUDITS", "")).strip()
    resolved_auth = (auth_token or os.getenv("SLB_AUTH_TOKEN", "")).strip()
    resolved_fail = fail_on_critical or _env_flag("SLB_FAIL_ON_CRITICAL", False)
    audit_list = [item.strip() for item in resolved_audits.split(",") if item.strip()] if resolved_audits else []
    return RuntimeSettings(
        url=resolved_url,
        output_dir=output_dir or config.REPORT_OUTPUT_DIR,
        audits=audit_list,
        auth_token=resolved_auth,
        fail_on_critical=resolved_fail,
    )


def select_active_evaluators(audits: Optional[str] = None) -> List[BaseEvaluator]:
    from modules.accessibility import AccessibilityEvaluator
    from modules.aeo_geo import AeoGeoEvaluator
    from modules.drupal import DrupalEvaluator
    from modules.pagespeed import PagespeedEvaluator
    from modules.seo import SeoEvaluator
    from modules.ux import UxEvaluator

    all_evaluators = [
        ("seo", SeoEvaluator),
        ("performance", PagespeedEvaluator),
        ("accessibility", AccessibilityEvaluator),
        ("aeo-geo", AeoGeoEvaluator),
        ("ux", UxEvaluator),
        ("security", DrupalEvaluator),
    ]
    if not audits:
        return [factory() for _, factory in all_evaluators]

    requested = {item.strip().lower() for item in audits.split(",") if item.strip()}
    if not requested or requested.intersection({"all", "*"}):
        return [factory() for _, factory in all_evaluators]

    aliases = {
        "seo": "seo",
        "performance": "performance",
        "accessibility": "accessibility",
        "aeo": "aeo-geo",
        "geo": "aeo-geo",
        "aeo-geo": "aeo-geo",
        "ux": "ux",
        "security": "security",
        "drupal": "security",
    }
    normalized = {aliases.get(item, item) for item in requested}
    selected = []
    for key, factory in all_evaluators:
        if key in normalized:
            selected.append(factory())
    return selected

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
    auth_token: Optional[str] = None
) -> List[EvaluationResult]:
    """
    Asynchronously crawls the target URL (recursively if crawl_depth > 0)
    and runs all specified evaluation modules concurrently, consolidating the results.
    Optional OntologyStore integration allows for DuckDB and LanceDB persistence.
    """
    from utils.ssrf_guard import SSRFGuard, SSRFViolationError
    from crawler import Crawler
    from modules.renderer import PlaywrightRenderer
    from urllib.parse import urlparse
    
    # 0. Validate SSRF Safety
    try:
        guard = SSRFGuard(allow_private=allow_private)
        await guard.validate(url)
    except SSRFViolationError as e:
        console.print(f"[bold red]Security Error: SSRF Protection blocked request to {url}[/bold red]")
        console.print(f"[red]{str(e)}[/red]")
        raise typer.Exit(code=1)
        
    crawled_pages: Dict[str, str] = {}
    crawler = None
    
    # 1. Resolve browser renderer/scraping engine strategy
    renderer = scraping_engine
    if not renderer and render:
        renderer = PlaywrightRenderer()
    
    # 2. Crawl Target Site
    client = httpx.AsyncClient(
        timeout=config.REQUEST_TIMEOUT,
        headers=config.build_request_headers(auth_token),
        http2=http2,
    )
    try:
        if crawl_depth > 0 or check_links:
            console.print(f"[bold blue]Initiating crawler (depth={crawl_depth if crawl_depth > 0 else 1}, max_urls={max_urls}, check_links={check_links})...[/bold blue]")
            crawler = Crawler(url, max_depth=crawl_depth if crawl_depth > 0 else 1, max_urls=max_urls, allow_private=allow_private)
            crawled_pages = await crawler.crawl(client, renderer)
            console.print(f"[bold green]✔ Crawler finished. Discovered {len(crawled_pages)} pages.[/bold green]")
            
            if crawl_depth == 0 and check_links:
                # Keep only start url in crawled_pages for full HTML evaluation, but keep crawler.broken_links!
                start_normalized = crawler.start_url
                matching_url = next((u for u in crawled_pages if urlparse(u).path == urlparse(start_normalized).path), start_normalized)
                crawled_pages = {matching_url: crawled_pages.get(matching_url, "")}
        else:
            try:
                if renderer:
                    console.print(f"[bold blue]Scraping page DOM using pluggable engine {type(renderer).__name__}...[/bold blue]")
                    if hasattr(renderer, "scrape"):
                        html_content = await renderer.scrape(url)
                    else:
                        html_content = await renderer.render(url)
                    crawled_pages[url] = html_content
                else:
                    response = await client.get(url, follow_redirects=True)
                    response.raise_for_status()
                    crawled_pages[str(response.url)] = response.text
            except Exception as e:
                console.print(f"[bold red]Error: Failed to fetch target URL: {url}[/bold red]")
                console.print(f"[red]{str(e)}[/red]")
                raise typer.Exit(code=1)
                
        # 2. Run Evaluator Modules Concurrently on all crawled pages
        all_eval_results: Dict[str, List[EvaluationResult]] = {mod.domain: [] for mod in active_modules}
        
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
            
            # Group results by domain
            for idx, r in enumerate(page_results):
                mod = active_modules[idx]
                if isinstance(r, Exception):
                    console.print(f"[bold yellow]Warning: Evaluator '{mod.domain}' failed on {page_url}: {str(r)}[/bold yellow]")
                else:
                    # Update issue locations to specify the page path
                    url_path = urlparse(page_url).path or "/"
                    updated_issues = []
                    for issue in r.issues:
                        updated_issues.append(replace(issue, location=f"[{url_path}] {issue.location}"))
                        if store and run_id:
                            await store.record_finding(
                                run_id=run_id,
                                page_url=page_url,
                                domain_id=mod.domain,
                                issue_id=issue.id,
                                severity=issue.severity,
                                message=issue.message,
                                location=issue.location,
                                remedy=issue.remedy
                            )
                    updated_r = replace(r, issues=tuple(updated_issues))
                    all_eval_results[mod.domain].append(updated_r)

        # 3. Consolidate results across all crawled pages
        consolidated_results: List[EvaluationResult] = []
        
        for mod in active_modules:
            domain_results = all_eval_results.get(mod.domain, [])
            if not domain_results:
                continue
                
            avg_score = sum(r.score for r in domain_results) / len(domain_results)
            
            all_issues = []
            for r in domain_results:
                all_issues.extend(r.issues)
                
            if mod.domain == "Technical SEO" and check_links and crawler and hasattr(crawler, "broken_links") and crawler.broken_links:
                updated_issues = list(all_issues)
                for b_link, status in crawler.broken_links.items():
                    updated_issues.append(Issue(
                        id="R-SEO-BROKEN-LINK",
                        severity=config.SEVERITY_WARNING,
                        message=f"Discovered broken outbound link: {b_link} returned status {status}.",
                        location="Link href reference",
                        remedy="Inspect and correct the destination URL or remove the inactive hyperlink reference."
                    ))
                all_issues = tuple(updated_issues)
                
            # Merge metadata
            merged_metadata = {"crawled_pages_count": len(domain_results)}
            for r in domain_results:
                for k, v in r.metadata.items():
                    if k not in merged_metadata:
                        merged_metadata[k] = v
                    elif isinstance(v, (int, float)):
                        merged_metadata[k] += v
                        
            consolidated_results.append(EvaluationResult(
                domain=mod.domain,
                score=round(avg_score, 1),
                issues=all_issues,
                metadata=merged_metadata
            ))
            
        if store and run_id:
            report_payload = build_report_payload(url, consolidated_results)
            await store.finish_run(run_id, report_payload, len(crawled_pages), len(consolidated_results))
    finally:
        close_result = client.aclose()
        if inspect.isawaitable(close_result):
            await close_result

    return consolidated_results

def print_terminal_report(url: str, results: List[EvaluationResult]):
    """
    Renders a stunning summary of the evaluation results in the console using Rich.
    """
    console.print("\n")
    console.print(Panel(
        f"[bold white]Audit Target:[/bold white] [cyan]{url}[/cyan]\n"
        f"[bold white]Total Modules Checked:[/bold white] {len(results)}",
        title="[bold green]Stealth Lightbeacon Diagnostics Summary[/bold green]",
        expand=False
    ))
    
    # 1. Overview Table
    summary_table = Table(title="Domain Evaluation Scores", show_header=True, header_style="bold magenta")
    summary_table.add_column("Domain", style="cyan", width=25)
    summary_table.add_column("Score", justify="right", style="bold")
    summary_table.add_column("Issues Detected", justify="right")
    summary_table.add_column("Verdict", style="dim")
    
    total_score = 0.0
    for r in results:
        total_score += r.score
        issues_count = len(r.issues)
        
        # Color-coded score styling
        if r.score >= 8.0:
            score_str = f"[green]{r.score:.1f}/10.0[/green]"
            verdict = "[green]Excellent[/green]"
        elif r.score >= 5.0:
            score_str = f"[yellow]{r.score:.1f}/10.0[/yellow]"
            verdict = "[yellow]Warning[/yellow]"
        else:
            score_str = f"[red]{r.score:.1f}/10.0[/red]"
            verdict = "[bold red]Critical Gaps[/bold red]"
            
        summary_table.add_row(r.domain, score_str, str(issues_count), verdict)
        
    avg_score = total_score / len(results) if results else 0.0
    summary_table.add_row(
        "[bold white]Average Score[/bold white]",
        f"[bold white]{avg_score:.1f}/10.0[/bold white]",
        "",
        ""
    )
    console.print(summary_table)
    
    # 2. Issues Breakdown Table
    issues_table = Table(title="Detailed Issue Log", show_header=True, header_style="bold red")
    issues_table.add_column("Domain", style="cyan", width=15)
    issues_table.add_column("ID", style="dim", width=10)
    issues_table.add_column("Severity", width=12)
    issues_table.add_column("Message")
    issues_table.add_column("Remedy", style="green")
    
    has_issues = False
    for r in results:
        for issue in r.issues:
            has_issues = True
            
            # Severity color
            if issue.severity == config.SEVERITY_CRITICAL:
                sev_str = f"[bold red]{issue.severity.upper()}[/bold red]"
            elif issue.severity == config.SEVERITY_WARNING:
                sev_str = f"[yellow]{issue.severity.upper()}[/yellow]"
            elif issue.severity == config.SEVERITY_INFO:
                sev_str = f"[blue]{issue.severity.upper()}[/blue]"
            else:
                sev_str = f"[green]{issue.severity.upper()}[/green]"
                
            issues_table.add_row(
                r.domain,
                issue.id,
                sev_str,
                issue.message,
                issue.remedy
            )
            
    if has_issues:
        console.print(issues_table)
    else:
        console.print("[bold green]✔ No critical issues detected! Perfect pass.[/bold green]")

def save_json_report(url: str, results: List[EvaluationResult], filepath: str):
    """
    Saves a detailed diagnostic report in JSON format.
    """
    report_data = build_report_payload(url, results)
        
    os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)
    console.print(f"[bold green]✔ Diagnostic JSON report written to: {filepath}[/bold green]")

@app.command()
def evaluate(
    url: Optional[str] = typer.Argument(None, help="The target URL of the Drupal site to scan (optional if using --watch or --search-semantic)."),
    output_dir: Optional[str] = typer.Option(None, "--out", "-o", help="Custom output folder path for reports."),
    audits: Optional[str] = typer.Option(None, "--audits", help="Comma-separated evaluator subset such as security,performance."),
    fail_on_critical: bool = typer.Option(False, "--fail-on-critical", help="Exit non-zero when any critical finding is present."),
    allow_private: bool = typer.Option(False, "--allow-private", help="Permit scans of private and loopback IP addresses (disables SSRF protection)."),
    crawl_depth: int = typer.Option(0, "--crawl-depth", "-d", help="Max recursion depth for crawl links discovery (0 resolves only the target URL)."),
    max_urls: int = typer.Option(10, "--max-urls", "-n", help="Max URLs circuit-breaker boundary during crawling."),
    render: bool = typer.Option(False, "--render", help="Enable JavaScript-rendered DOM auditing using headless Playwright."),
    http2: bool = typer.Option(False, "--http2", help="Enable HTTP/2 support for connection requests."),
    report_format: str = typer.Option("both", "--format", "-f", help="Output report format: 'json', 'html', 'both', 'llm', or 'geo-xml'."),
    engine: str = typer.Option("http", "--engine", help="Adversarial scraping engine strategy: 'http', 'fast', 'stealth', or 'mcp'."),
    recon: bool = typer.Option(False, "--recon", help="Run advisory anti-bot reconnaissance before the audit."),
    recon_auto: bool = typer.Option(False, "--recon-auto", help="Automatically apply the recon-recommended scraping posture."),
    budget: Optional[str] = typer.Option(None, "--budget", help="Path to a JSON configuration file defining performance budgets (e.g. LCP, CLS thresholds)."),
    check_links: bool = typer.Option(False, "--check-links", help="Enable Outbound Broken Link Checker scanning."),
    check_api: bool = typer.Option(False, "--check-api", help="Enable default Drupal JSON:API and REST directories scanning."),
    persist: bool = typer.Option(False, "--persist", help="Enable DuckDB/LanceDB dual persistence storage."),
    watch: bool = typer.Option(False, "--watch", help="Start the live WorkspaceWatcher on the current directory."),
    search_semantic: Optional[str] = typer.Option(None, "--search-semantic", help="Perform a semantic vector search query on historical run data.")
):
    """
    Evaluates the target website on SEO, Performance (PageSpeed), Accessibility, and AEO/GEO metrics.
    """
    if search_semantic:
        from utils.ontology import OntologyStore
        store = OntologyStore()
        try:
            results = store.search(search_semantic, limit=5)
            console.print(f"\n[bold green]✔ Semantic Search Results for: '{search_semantic}'[/bold green]\n")
            if not results:
                console.print("[dim]No results found.[/dim]")
            for idx, res in enumerate(results):
                console.print(f"[bold cyan]{idx+1}. [{res['kind'].upper()}] {res['label']}[/bold cyan] (Score: {res['score']})")
                console.print(f"  [dim]Text: {res['text']}[/dim]")
                if res.get('url'):
                    console.print(f"  [dim]URL: {res['url']}[/dim]")
                console.print("")
        finally:
            store.close()
        return

    if watch:
        import signal
        import time
        from utils.watcher import WorkspaceWatcher
        watcher = WorkspaceWatcher(workspace_root=".")
        watcher.start()
        
        def signal_handler(signum, frame):
            console.print("\n[bold yellow]Gracefully shutting down WorkspaceWatcher...[/bold yellow]")
            watcher.stop()
            raise typer.Exit(code=0)
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        console.print("[bold green]✔ WorkspaceWatcher is active. Press Ctrl+C to exit.[/bold green]")
        while True:
            try:
                time.sleep(1)
            except (KeyboardInterrupt, SystemExit):
                watcher.stop()
                break
        return

    runtime = build_runtime_settings(
        url=url,
        audits=audits,
        fail_on_critical=fail_on_critical,
        output_dir=output_dir,
    )
    if not runtime.url:
        console.print("[bold red]Error: Missing target URL. Set SLB_TARGET_URL or pass a URL argument.[/bold red]")
        raise typer.Exit(code=1)

    try:
        from report.generator import ReportGenerator
        from modules.scraping import ScrapingFactory
    except ImportError as e:
        console.print(f"[bold red]Setup Error: Evaluator or Report modules failed to import.[/bold red]")
        console.print(f"[red]{str(e)}[/red]")
        raise typer.Exit(code=1)
        
    if render or engine.lower().strip() in ["stealth", "mcp"]:
        from modules.renderer import PLAYWRIGHT_AVAILABLE
        if not PLAYWRIGHT_AVAILABLE:
            console.print(f"[bold red]Error: Playwright is not installed in the environment.[/bold red]")
            console.print(f"Scraping/rendering mode '{engine if not render else 'render'}' requires the 'playwright' package.")
            console.print(f"To install it, run: [bold green]pip install playwright && playwright install[/bold green]")
            raise typer.Exit(code=1)
        
    active_evaluators = select_active_evaluators(",".join(runtime.audits) if runtime.audits else None)
    if not active_evaluators:
        console.print("[bold red]Error: No evaluators selected for the requested audits.[/bold red]")
        raise typer.Exit(code=1)
    
    target_out_dir = runtime.output_dir
    json_path = os.path.join(target_out_dir, "report.json")
    llm_path = os.path.join(target_out_dir, "report.md")
    geo_xml_path = os.path.join(target_out_dir, "report.xml")
    
    console.print(f"[bold blue]Starting audit for target website:[/bold blue] [cyan]{runtime.url}[/cyan]\n")

    recon_recommendation = None
    if recon or recon_auto:
        from utils.recon import ReconAdvisor
        recon_recommendation = asyncio.run(ReconAdvisor().inspect(runtime.url))
        console.print(
            f"[dim]Recon posture: {recon_recommendation.posture} | engine: {recon_recommendation.recommended_engine} | confidence: {recon_recommendation.confidence:.2f}[/dim]"
        )
        if recon_auto:
            engine = recon_recommendation.recommended_engine
    
    # Resolve custom scraping engine if a specific strategy is selected
    scraping_engine = ScrapingFactory.get_engine(engine, allow_private=allow_private)
    
    store = None
    run_id = None
    if persist:
        import uuid
        from datetime import datetime, timezone
        from utils.ontology import OntologyStore
        store = OntologyStore()
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        
        # Call begin_run synchronously
        asyncio.run(store.begin_run(
            run_id=run_id,
            target_url=runtime.url,
            started_at=datetime.now(timezone.utc).isoformat(),
            options={
                "crawl_depth": crawl_depth,
                "max_urls": max_urls,
                "render": render,
                "http2": http2,
                "engine": engine,
                "check_links": check_links,
                "check_api": check_api,
                "audits": runtime.audits,
                "fail_on_critical": runtime.fail_on_critical,
                "recon": recon,
                "recon_auto": recon_auto,
            }
        ))

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True
        ) as progress:
            progress.add_task(description="Crawling and running evaluator algorithms...", total=None)
            # Execute async loop
            results = asyncio.run(run_evaluation(
                runtime.url,
                active_evaluators,
                allow_private=allow_private,
                crawl_depth=crawl_depth,
                max_urls=max_urls,
                render=render,
                http2=http2,
                scraping_engine=scraping_engine,
                check_links=check_links,
                check_api=check_api,
                store=store,
                run_id=run_id,
                auth_token=runtime.auth_token,
            ))
    finally:
        if store:
            store.close()
        
    # Render Console Tables
    print_terminal_report(runtime.url, results)
    
    # Save Reports
    payload = build_report_payload(runtime.url, results)
    try:
        if report_format.lower() in ["json", "both"]:
            save_json_report(runtime.url, results, json_path)
        elif report_format.lower() == "llm":
            with open(llm_path, "w", encoding="utf-8") as handle:
                handle.write(render_report_format("llm", payload))
            console.print(f"[bold green]✔ Diagnostic Markdown report written to: {llm_path}[/bold green]")
        elif report_format.lower() == "geo-xml":
            with open(geo_xml_path, "w", encoding="utf-8") as handle:
                handle.write(render_report_format("geo-xml", payload))
            console.print(f"[bold green]✔ Diagnostic GEO XML report written to: {geo_xml_path}[/bold green]")
        elif report_format.lower() != "html":
            console.print(f"[bold red]Error: Unsupported report format '{report_format}'.[/bold red]")
            raise typer.Exit(code=1)
    except ValueError as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        raise typer.Exit(code=1)
    
    # Generate HTML Report
    if report_format.lower() in ["html", "both"]:
        try:
            ReportGenerator.generate_report(runtime.url, results, target_out_dir)
            console.print(f"[bold green]✔ Diagnostic HTML report written to: {os.path.join(target_out_dir, 'report.html')}[/bold green]")
        except Exception as e:
            console.print(f"[yellow]Warning: Failed to generate HTML report: {str(e)}[/yellow]")

    # Check performance budgets if requested
    if budget:
        if not os.path.exists(budget):
            console.print(f"[bold red]Error: Budget configuration file not found at: {budget}[/bold red]")
            raise typer.Exit(code=1)
        try:
            with open(budget, "r", encoding="utf-8") as f:
                budget_data = json.load(f)
            from utils.budget_validator import BudgetValidator
            validator = BudgetValidator(budget_data)
            budget_failures = validator.validate(results)
            
            if budget_failures:
                console.print("\n[bold red]✖ Performance Budget Validation Failed:[/bold red]")
                for failure in budget_failures:
                    console.print(f"[red]  - {failure}[/red]")
                raise typer.Exit(code=2)
            else:
                console.print("\n[bold green]✔ Performance Budget Validation Passed successfully![/bold green]")
        except typer.Exit as te:
            raise te
        except Exception as e:
            console.print(f"[bold red]Error parsing budget configuration: {str(e)}[/bold red]")
            raise typer.Exit(code=1)

    if runtime.fail_on_critical and any(issue.severity == config.SEVERITY_CRITICAL for result in results for issue in result.issues):
        console.print("[bold red]Critical findings detected and --fail-on-critical is enabled.[/bold red]")
        raise typer.Exit(code=1)
 
if __name__ == "__main__":
    app()
