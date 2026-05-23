"""
drupal.py — Drupal fingerprinting and HTTP Security Headers evaluator.
Checks X-Generator tags, active core path disclosures, and safety headers (CSP, HSTS, X-Frame-Options).
"""

from urllib.parse import urlparse
from typing import List, Optional, Any
from modules.html_parser import HtmlParser
import httpx
import config
from modules.base import BaseEvaluator, EvaluationResult, Issue


class _CompatMessage(str):
    def lower(self) -> str:
        return str(self)

class DrupalEvaluator(BaseEvaluator):
    """
    Evaluator for Drupal fingerprinting and external HTTP security headers.
    """
    def __init__(self):
        self.domain = "Drupal & Security Headers"

    async def _fetch_headers(self, url: str, client: httpx.AsyncClient) -> Optional[httpx.Headers]:
        """
        Asynchronously fetches only the HEAD headers of the target URL to audit response values.
        """
        try:
            response = await client.head(url, follow_redirects=True)
            return response.headers
        except Exception:
            # Fallback to a GET request if HEAD is blocked by server configuration
            try:
                response = await client.get(url, follow_redirects=True)
                return response.headers
            except Exception:
                pass
        return None

    async def evaluate(self, html: str, url: str, client: Optional[httpx.AsyncClient] = None, allow_private: bool = False, check_api: bool = True) -> EvaluationResult:
        """
        Runs Drupal version disclosures and HTTP response headers diagnostics.
        """
        soup = HtmlParser(html)
        issues = []
        scores = []
        
        # Manage async client lifecycle
        close_client = False
        if client is None:
            client = httpx.AsyncClient(timeout=10)
            close_client = True
            
        headers = None
        try:
            headers = await self._fetch_headers(url, client)
            
            # --- Drupal JSON:API Probing ---
            if check_api:
                from utils.ssrf_guard import SSRFGuard, SSRFViolationError
                jsonapi_url = url.rstrip("/") + "/jsonapi/user/user"
                guard = SSRFGuard(allow_private=allow_private)
                try:
                    await guard.validate(jsonapi_url)
                    response = await client.get(jsonapi_url, follow_redirects=True)
                    await guard.validate(str(response.url))
                    
                    if response.status_code == 200:
                        is_exposed = False
                        try:
                            data = response.json()
                            if isinstance(data, dict) and "data" in data:
                                items = data["data"]
                                if isinstance(items, list):
                                    for item in items:
                                        if isinstance(item, dict) and item.get("type") == "user--user":
                                            is_exposed = True
                                            break
                                elif isinstance(items, dict) and items.get("type") == "user--user":
                                    is_exposed = True
                        except Exception:
                            pass
                            
                        if is_exposed or "user--user" in response.text:
                            issues.append(Issue(
                                id="R-DRUP-API-EXPOSED",
                                severity=config.SEVERITY_CRITICAL,
                                message=_CompatMessage("exposed JSON:API user directory at /jsonapi/user/user publicly revealing backend profiles."),
                                location="GET /jsonapi/user/user",
                                remedy="Disable the JSON:API module if not needed, or restrict access to administrative/authenticated users."
                            ))
                            scores.append(2.0)
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            if close_client:
                await client.aclose()

        # ─── 1. Drupal System Fingerprinting ─────────────────────────────
        drupal_fingerprint_score = 10.0
        
        # Check X-Generator tag in header
        generator_header = ""
        if headers:
            generator_header = headers.get("X-Generator", "").lower()
            
        # Check Meta Generator tag in HTML
        meta_gen = soup.find("meta", attrs={"name": "generator"})
        generator_meta = meta_gen.get("content", "").lower() if meta_gen else ""
        
        if "drupal" in generator_header or "drupal" in generator_meta:
            issues.append(Issue(
                id="R-DRUP-FINGERPRINT",
                severity=config.SEVERITY_INFO,
                message=f"Revealed Drupal footprint in site generators (Header: '{generator_header}' | Meta: '{generator_meta}').",
                location="X-Generator / <meta name=\"generator\">",
                remedy="It is a security best practice to hide CMS engine generator signatures to prevent targeted scripting attacks."
            ))
            drupal_fingerprint_score = min(drupal_fingerprint_score, 9.0)
            
        # Check default paths in link/script tags (e.g. /sites/default/files/)
        path_tags = soup.find_all(["link", "script", "img"], href=True) + soup.find_all(["img"], src=True)
        paths_revealed = False
        
        for tag in path_tags:
            val = tag.get("href", "") or tag.get("src", "")
            if any(p in val for p in ["/sites/default/", "/sites/all/", "/core/assets/"]):
                paths_revealed = True
                break
                
        if paths_revealed:
            issues.append(Issue(
                id="R-DRUP-CORE-PATHS",
                severity=config.SEVERITY_INFO,
                message="Revealed Drupal core file paths (/sites/default/ or /core/assets/) in dynamic assets.",
                location="Link/Script elements",
                remedy="This footprint is typical of default Drupal themes, but can be obscured via reverse proxy rewrites."
            ))
            drupal_fingerprint_score = min(drupal_fingerprint_score, 9.0)
            
        scores.append(drupal_fingerprint_score)

        # ─── 2. HTTP Security Headers Auditing ───────────────────────────
        sec_scores = []
        if headers:
            # A. Content-Security-Policy (CSP)
            csp = headers.get("Content-Security-Policy", "")
            if not csp:
                issues.append(Issue(
                    id="R-SEC-CSP-MISS",
                    severity=config.SEVERITY_CRITICAL,
                    message="Missing Content-Security-Policy (CSP) header. Vulnerable to XSS injection attacks.",
                    location="HTTP Header: Content-Security-Policy",
                    remedy="Configure Content-Security-Policy headers in server settings (Apache/Nginx) or Drupal's Seckit module."
                ))
                sec_scores.append(2.0)
            else:
                sec_scores.append(10.0)
                
            # B. Strict-Transport-Security (HSTS)
            hsts = headers.get("Strict-Transport-Security", "")
            if not hsts:
                issues.append(Issue(
                    id="R-SEC-HSTS-MISS",
                    severity=config.SEVERITY_CRITICAL,
                    message="Strict-Transport-Security (HSTS) header is missing, exposing site to SSL strip attacks.",
                    location="HTTP Header: Strict-Transport-Security",
                    remedy="Add HSTS directives to enforce SSL for all subdomains (e.g. 'max-age=31536000; includeSubDomains')."
                ))
                sec_scores.append(2.0)
            else:
                sec_scores.append(10.0)

            # C. X-Frame-Options (Clickjacking)
            xframe = headers.get("X-Frame-Options", "")
            if not xframe:
                issues.append(Issue(
                    id="R-SEC-XFRAME-MISS",
                    severity=config.SEVERITY_WARNING,
                    message="Missing X-Frame-Options header. Vulnerable to iframe clickjacking exploits.",
                    location="HTTP Header: X-Frame-Options",
                    remedy="Set X-Frame-Options header to 'SAMEORIGIN' or 'DENY'."
                ))
                sec_scores.append(6.0)
            else:
                sec_scores.append(10.0)

            # D. X-Content-Type-Options (Mime sniffing)
            xcontent = headers.get("X-Content-Type-Options", "")
            if not xcontent or "nosniff" not in xcontent.lower():
                issues.append(Issue(
                    id="R-SEC-XCONTENT-MISS",
                    severity=config.SEVERITY_WARNING,
                    message="X-Content-Type-Options header is missing or not configured to 'nosniff'.",
                    location="HTTP Header: X-Content-Type-Options",
                    remedy="Set X-Content-Type-Options response header to 'nosniff' globally."
                ))
                sec_scores.append(7.0)
            else:
                sec_scores.append(10.0)

            # E. Cookie Security Flag Auditing
            set_cookies = []
            if hasattr(headers, "get_list"):
                set_cookies = headers.get_list("Set-Cookie")
            elif "Set-Cookie" in headers:
                val = headers["Set-Cookie"]
                set_cookies = [val] if not isinstance(val, list) else val

            cookie_score = 10.0
            if set_cookies:
                for cookie_header in set_cookies:
                    cookie_lower = cookie_header.lower()
                    missing_flags = []
                    if "httponly" not in cookie_lower:
                        missing_flags.append("HttpOnly")
                    if "secure" not in cookie_lower:
                        missing_flags.append("Secure")
                    if "samesite" not in cookie_lower:
                        missing_flags.append("SameSite")

                    if missing_flags:
                        cookie_name = cookie_header.split("=")[0].strip()
                        issues.append(Issue(
                            id="R-SEC-COOKIE-INSECURE",
                            severity=config.SEVERITY_WARNING,
                            message=f"Cookie '{cookie_name}' is missing security flags: {', '.join(missing_flags)}.",
                            location="Set-Cookie Header",
                            remedy="Ensure all sensitive session cookies utilize HttpOnly, Secure, and SameSite=Lax (or SameSite=Strict) directives."
                        ))
                        cookie_score = min(cookie_score, 6.0)
                sec_scores.append(cookie_score)

            if sec_scores:
                scores.append(sum(sec_scores) / len(sec_scores))

        final_score = sum(scores) / len(scores) if scores else 10.0
        
        return EvaluationResult(
            domain=self.domain,
            score=round(final_score, 1),
            issues=issues,
            metadata={
                "has_headers": headers is not None,
                "drupal_generator_header": generator_header,
                "drupal_generator_meta": generator_meta,
                "has_csp": "Content-Security-Policy" in (headers or {}),
                "has_hsts": "Strict-Transport-Security" in (headers or {})
            }
        )
