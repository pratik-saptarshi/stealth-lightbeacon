"""
seo.py — Technical SEO evaluator. Performs Canonical URL validation, metadata validation,
Schema.org JSON-LD decoding, and indexability audits (robots.txt and sitemaps).
"""

import json
from urllib.parse import urlparse, urljoin
from typing import Dict, Any, List, Optional
import httpx
from modules.html_parser import HtmlParser
import config
from modules.base import BaseEvaluator, EvaluationResult, Issue


def _safe_text(value: Any) -> str:
    return str(value or "").strip()

class SeoEvaluator(BaseEvaluator):
    """
    Evaluator for technical SEO. Analyzes canonical tags, structured JSON-LD, metadata, sitemaps, and robots.txt.
    """
    def __init__(self):
        self.domain = "Technical SEO"

    async def _fetch_robots_txt(self, base_url: str, client: httpx.AsyncClient) -> Optional[str]:
        """
        Asynchronously fetches the robots.txt file from the root domain.
        """
        parsed_url = urlparse(base_url)
        robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"
        try:
            response = await client.get(robots_url, follow_redirects=True)
            if response.status_code == 200:
                return response.text
        except Exception:
            pass
        return None

    async def evaluate(self, html: str, url: str, client: Optional[httpx.AsyncClient] = None, allow_private: bool = False) -> EvaluationResult:
        """
        Executes static HTML analysis and external indexing audits for SEO.
        """
        soup = HtmlParser(html)
        issues = []
        scores = []
        
        # Define clean URL parsing
        parsed_url = urlparse(url)
        
        # Manage async client lifecycle
        close_client = False
        if client is None:
            client = httpx.AsyncClient(timeout=10)
            close_client = True
            
        try:
            # Fetch and parse robots.txt
            robots_txt = await self._fetch_robots_txt(url, client)
        except Exception:
            robots_txt = None
        finally:
            if close_client:
                await client.aclose()

        # ─── 1. Canonical URL Audit ──────────────────────────────────────
        canonical_tag = soup.find("link", rel="canonical")
        if not canonical_tag:
            issues.append(Issue(
                id="R-SEO-CAN-MISS",
                severity=config.SEVERITY_CRITICAL,
                message="Missing canonical URL link tag (<link rel=\"canonical\">).",
                location="<head>",
                remedy="Install Drupal's Metatag module and configure canonical URL fields globally."
            ))
            scores.append(2.0)
        else:
            canonical_href = _safe_text(canonical_tag.get("href"))
            if not canonical_href:
                issues.append(Issue(
                    id="R-SEO-CAN-EMPTY",
                    severity=config.SEVERITY_CRITICAL,
                    message="Canonical link tag has an empty href attribute.",
                    location="<link rel=\"canonical\">",
                    remedy="Validate the canonical URL settings inside your theme or Metatag module configurations."
                ))
                scores.append(3.0)
            else:
                # Check HTTP vs HTTPS mismatch
                parsed_canonical = urlparse(canonical_href)
                if parsed_canonical.scheme == "http" and parsed_url.scheme == "https":
                    issues.append(Issue(
                        id="R-SEO-CAN-SCHEME",
                        severity=config.SEVERITY_WARNING,
                        message=f"Canonical scheme is insecure HTTP ({canonical_href}) while requesting secure HTTPS page.",
                        location="<link rel=\"canonical\">",
                        remedy="Enforce HTTPS schemes globally in your Drupal settings.php and canonical templates."
                    ))
                    scores.append(6.0)
                # Check Self-referencing Canonical URL
                elif parsed_canonical.path != parsed_url.path or parsed_canonical.netloc != parsed_url.netloc:
                    issues.append(Issue(
                        id="R-SEO-CAN-MISMATCH",
                        severity=config.SEVERITY_WARNING,
                        message=f"Canonical link points to a different page ({canonical_href}) instead of self-referencing.",
                        location="<link rel=\"canonical\">",
                        remedy="Ensure that the canonical tag matches the unique page URL (or cross-domain URL if intended)."
                    ))
                    scores.append(7.0)
                else:
                    scores.append(10.0)

        # ─── 2. Structured Data / Schema.org Validation ───────────────────
        json_ld_scripts = soup.find_all("script", type="application/ld+json")
        if not json_ld_scripts:
            issues.append(Issue(
                id="R-SEO-LD-MISS",
                severity=config.SEVERITY_CRITICAL,
                message="Missing structured Schema.org data (no JSON-LD script blocks found).",
                location="Entire DOM",
                remedy="Enable structured JSON-LD outputs in your Drupal templates, or use the Schema.org Metatag module."
            ))
            scores.append(3.0)
        else:
            ld_scores = []
            for idx, script in enumerate(json_ld_scripts):
                script_content = script.string
                if not script_content:
                    issues.append(Issue(
                        id=f"R-SEO-LD-EMPTY-{idx}",
                        severity=config.SEVERITY_WARNING,
                        message=f"JSON-LD script block #{idx} is empty.",
                        location=f"<script type=\"application/ld+json\"> block #{idx}",
                        remedy="Verify that custom structured data plugins are supplying active data structures."
                    ))
                    ld_scores.append(4.0)
                    continue
                    
                try:
                    ld_json = json.loads(script_content)
                    # Verify core context and type properties
                    context = ld_json.get("@context", "")
                    ld_type = ld_json.get("@type", "")
                    
                    if "schema.org" not in str(context):
                        issues.append(Issue(
                            id=f"R-SEO-LD-CTX-{idx}",
                            severity=config.SEVERITY_WARNING,
                            message=f"JSON-LD schema block #{idx} has incorrect or missing @context reference ({context}).",
                            location=f"<script type=\"application/ld+json\"> block #{idx}",
                            remedy="Ensure @context is set exactly to 'https://schema.org'."
                        ))
                        ld_scores.append(6.0)
                    elif not ld_type:
                        issues.append(Issue(
                            id=f"R-SEO-LD-TYPE-{idx}",
                            severity=config.SEVERITY_WARNING,
                            message=f"JSON-LD block #{idx} is missing a defined @type entity declaration.",
                            location=f"<script type=\"application/ld+json\"> block #{idx}",
                            remedy="Explicitly declare target entity types (e.g., 'Article', 'Organization', 'WebSite')."
                        ))
                        ld_scores.append(7.0)
                    else:
                        ld_scores.append(10.0)
                except json.JSONDecodeError:
                    issues.append(Issue(
                        id=f"R-SEO-LD-PARSE-{idx}",
                        severity=config.SEVERITY_CRITICAL,
                        message=f"JSON-LD script block #{idx} contains invalid, malformed JSON structure.",
                        location=f"<script type=\"application/ld+json\"> block #{idx}",
                        remedy="Check for trailing commas, unescaped quotes, or syntax bugs in custom Schema.org configurations."
                    ))
                    ld_scores.append(2.0)
            
            avg_ld_score = sum(ld_scores) / len(ld_scores) if ld_scores else 8.0
            scores.append(avg_ld_score)

        # ─── 3. Metadata & Tag Hierarchy Validation ──────────────────────
        # Title Tag
        title_tag = soup.find("title")
        title_text = _safe_text(title_tag.string) if title_tag else ""
        if not title_tag or not title_text:
            issues.append(Issue(
                id="R-SEO-TITLE-MISS",
                severity=config.SEVERITY_CRITICAL,
                message="Missing page title tag (<title>).",
                location="<head>",
                remedy="Add a default title template in Drupal Metatag configurations."
            ))
            scores.append(2.0)
        else:
            title_len = len(title_text)
            if title_len < 10 or title_len > 60:
                issues.append(Issue(
                    id="R-SEO-TITLE-LEN",
                    severity=config.SEVERITY_WARNING,
                    message=f"Page title is suboptimal ({title_len} chars). Standard SEO limits are between 10 and 60 characters.",
                    location="<title>",
                    remedy="Update the title schema (e.g., '[node:title] | [site:name]') to produce descriptive titles."
                ))
                scores.append(7.0)
            else:
                scores.append(10.0)

        # Meta Description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if not meta_desc or not _safe_text(meta_desc.get("content")):
            issues.append(Issue(
                id="R-SEO-DESC-MISS",
                severity=config.SEVERITY_CRITICAL,
                message="Missing meta description tag (<meta name=\"description\">).",
                location="<head>",
                remedy="Set up descriptive summary tokens in Drupal's global Metatag definitions."
            ))
            scores.append(2.0)
        else:
            desc_len = len(_safe_text(meta_desc.get("content")))
            if desc_len < 110 or desc_len > 160:
                issues.append(Issue(
                    id="R-SEO-DESC-LEN",
                    severity=config.SEVERITY_WARNING,
                    message=f"Meta description is suboptimal ({desc_len} chars). Standard target is between 110 and 160 characters.",
                    location="<meta name=\"description\">",
                    remedy="Keep summary excerpts concise without cutting off descriptive context."
                ))
                scores.append(7.0)
            else:
                scores.append(10.0)

        # OpenGraph presence
        og_title = soup.find("meta", property="og:title")
        if not og_title:
            issues.append(Issue(
                id="R-SEO-OG-MISS",
                severity=config.SEVERITY_WARNING,
                message="Missing OpenGraph metadata tag (<meta property=\"og:title\">).",
                location="<head>",
                remedy="Enable OpenGraph extensions in Drupal Metatag configurations."
            ))
            scores.append(8.0)
        else:
            scores.append(10.0)

        # ─── 4. Crawlability & Indexability ──────────────────────────────
        # Robots Index Directives
        meta_robots = soup.find("meta", attrs={"name": "robots"})
        if meta_robots:
            content_robots = _safe_text(meta_robots.get("content")).lower()
            if "noindex" in content_robots:
                issues.append(Issue(
                    id="R-SEO-ROBOTS-NOINDEX",
                    severity=config.SEVERITY_WARNING,
                    message=f"Page robots tag is set to '{content_robots}', blocking search engines from indexing.",
                    location="<meta name=\"robots\">",
                    remedy="Verify environment index locks (staging settings.php or robots settings) and adjust to 'index, follow'."
                ))
                scores.append(5.0)
            else:
                scores.append(10.0)
        else:
            scores.append(10.0)

        # robots.txt fetch and verification
        if not robots_txt:
            issues.append(Issue(
                id="R-SEO-ROBOTS-MISS",
                severity=config.SEVERITY_WARNING,
                message="Failed to fetch robots.txt file, or file is empty.",
                location="/robots.txt",
                remedy="Generate a standard Drupal robots.txt in your web root directory."
            ))
            scores.append(7.0)
        else:
            import urllib.robotparser
            rp = urllib.robotparser.RobotFileParser()
            rp.parse(robots_txt.splitlines())
            
            home_url = f"{parsed_url.scheme}://{parsed_url.netloc}/"
            global_blocked = not rp.can_fetch("*", home_url)
            target_blocked = not rp.can_fetch("*", url)
            
            if global_blocked:
                issues.append(Issue(
                    id="R-SEO-ROBOTS-BLOCK",
                    severity=config.SEVERITY_CRITICAL,
                    message="robots.txt contains a global disallow directive, blocking all search engine crawlers from the site.",
                    location="/robots.txt",
                    remedy="Remove 'Disallow: /' from production robots.txt and replace with standard administrative restrictions."
                ))
                scores.append(1.0)
            elif target_blocked:
                issues.append(Issue(
                    id="R-SEO-ROBOTS-PATH-BLOCK",
                    severity=config.SEVERITY_WARNING,
                    message=f"robots.txt disallow directives block search engines from crawling the target URL ({url}).",
                    location="/robots.txt",
                    remedy="Review robots.txt path disallow rules and ensure public content is crawlable."
                ))
                scores.append(4.0)
            else:
                scores.append(10.0)
                
            # Check if Sitemap link is referenced using site_maps()
            sitemaps = rp.site_maps()
            if not sitemaps:
                issues.append(Issue(
                    id="R-SEO-ROBOTS-SITEMAP",
                    severity=config.SEVERITY_WARNING,
                    message="Sitemap URL reference is missing from robots.txt.",
                    location="/robots.txt",
                    remedy="Append a sitemap path reference (e.g., 'Sitemap: https://yourdomain.com/sitemap.xml') to robots.txt."
                ))
                scores.append(8.0)
            else:
                scores.append(10.0)
                
        final_score = sum(scores) / len(scores) if scores else 8.0
        if any(issue.id == "R-SEO-ROBOTS-BLOCK" for issue in issues):
            final_score = min(final_score, 4.0)
        
        return EvaluationResult(
            domain=self.domain,
            score=round(final_score, 1),
            issues=issues,
            metadata={
                "has_canonical": canonical_tag is not None,
                "json_ld_count": len(json_ld_scripts),
                "title_length": len(title_tag.string.strip()) if (title_tag and title_tag.string) else 0,
                "robots_txt_indexed": robots_txt is not None
            }
        )
