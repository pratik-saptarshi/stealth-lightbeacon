"""
ux.py — Static UX Performance evaluator.
Audits mobile viewport tags, inline font-size configurations, and tap-target spacings.
"""

import re
from typing import List, Optional, Any
from modules.html_parser import HtmlParser
import config
from modules.base import BaseEvaluator, EvaluationResult, Issue


def _safe_text(value: Any) -> str:
    return str(value or "").strip()

class UxEvaluator(BaseEvaluator):
    """
    Evaluator for static UX performance and mobile usability heuristics.
    """
    def __init__(self):
        self.domain = "UX Performance"

    async def evaluate(self, html: str, url: str, client: Optional[Any] = None, allow_private: bool = False) -> EvaluationResult:
        """
        Performs static layout and viewport heuristics for UX auditing.
        """
        soup = HtmlParser(html)
        issues = []
        scores = []

        # ─── 1. Viewport Configuration Tag (Mobile Usability) ────────────
        viewport = soup.find("meta", attrs={"name": "viewport"})
        if not viewport:
            issues.append(Issue(
                id="R-UX-VIEWPORT-MISS",
                severity=config.SEVERITY_CRITICAL,
                message="Missing viewport metadata tag (<meta name=\"viewport\">).",
                location="<head>",
                remedy="Always add '<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">' to support mobile responsive layouts."
            ))
            scores.append(2.0)
        else:
            content = _safe_text(viewport.get("content")).lower()
            if "width=device-width" not in content:
                issues.append(Issue(
                    id="R-UX-VIEWPORT-WIDTH",
                    severity=config.SEVERITY_WARNING,
                    message="Viewport meta tag is missing width=device-width parameter.",
                    location="<meta name=\"viewport\">",
                    remedy="Ensure viewport is configured to adjust to device width."
                ))
                scores.append(6.0)
            else:
                scores.append(10.0)

        # ─── 2. Small Font Size Warning (Readability) ────────────────────
        inline_styles = soup.find_all(style=True)
        small_font_count = 0
        
        for idx, tag in enumerate(inline_styles):
            style = _safe_text(tag.get("style")).lower()
            # Match font-size with small px values (e.g., font-size: 10px or font-size: 8px)
            match = re.search(r"font-size\s*:\s*(\d+)\s*px", style)
            if match:
                size = int(match.group(1))
                if size < 12:
                    small_font_count += 1
                    issues.append(Issue(
                        id=f"R-UX-FONT-SMALL-{idx}",
                        severity=config.SEVERITY_WARNING,
                        message=f"Text has inline font size too small for comfortable reading: {size}px",
                        location=str(tag)[:100],
                        remedy="Ensure all readable body text is at least 12px (preferably 16px) for visibility."
                    ))
                    
        if small_font_count > 0:
            scores.append(7.0)
        else:
            scores.append(10.0)

        # ─── 3. Navigation Menu Depth (Navigational Loop) ────────────────
        # Look for navigation menus (nav, ul[class*="menu"], etc.)
        nav_elements = soup.find_all(["nav", "ul"])
        max_depth = 0
        
        for nav in nav_elements:
            class_list = "".join(str(item) for item in (nav.get("class") or [])).lower()
            id_str = _safe_text(nav.get("id")).lower()
            
            if "menu" in class_list or "menu" in id_str or nav.name == "nav":
                # Find maximum nesting level of ul/ol tags
                nested_lists = nav.find_all(["ul", "ol"])
                depth = 1
                for nested in nested_lists:
                    # Count parent lists up to the current nav container
                    parents = len([p for p in nested.parents if p.name in ["ul", "ol"]]) + 1
                    depth = max(depth, parents)
                max_depth = max(max_depth, depth)
                
        if max_depth > 3:
            issues.append(Issue(
                id="R-UX-NAV-DEPTH",
                severity=config.SEVERITY_WARNING,
                message=f"Navigation menu has deep nesting hierarchy ({max_depth} levels).",
                location="Menu outline structures",
                remedy="Flatten menu structures to a maximum depth of 3 levels to improve user journey accessibility."
            ))
            scores.append(7.0)
        else:
            scores.append(10.0)

        # ─── 4. Tap Target Spacing Approximations (Touch Targets) ────────
        # Check inline styles for small heights or close margins on buttons
        interactive_tags = soup.find_all(["button", "a"])
        target_score = 10.0
        tap_issue_index = 1
        
        for tag in interactive_tags:
            style = _safe_text(tag.get("style")).lower()
            tag_flagged = False
            
            # Checks for height/width under 48px (standard Google UX threshold)
            height_match = re.search(r"height\s*:\s*(\d+)\s*px", style)
            width_match = re.search(r"width\s*:\s*(\d+)\s*px", style)
            
            if height_match:
                h_val = int(height_match.group(1))
                if h_val < 48:
                    issues.append(Issue(
                        id=f"R-UX-TAP-HEIGHT-{tap_issue_index}",
                        severity=config.SEVERITY_WARNING,
                        message=f"Interactive element tap target height is too small ({h_val}px). Google target is 48px.",
                        location=str(tag)[:100],
                        remedy="Provide minimum interactive button sizes of 48x48px to allow precise touch operations."
                    ))
                    target_score = min(target_score, 7.0)
                    tag_flagged = True
                    
            if width_match:
                w_val = int(width_match.group(1))
                if w_val < 48:
                    issues.append(Issue(
                        id=f"R-UX-TAP-WIDTH-{tap_issue_index}",
                        severity=config.SEVERITY_WARNING,
                        message=f"Interactive element tap target width is too small ({w_val}px). Google target is 48px.",
                        location=str(tag)[:100],
                        remedy="Configure interactive elements to occupy a minimum touch area of 48px."
                    ))
                    target_score = min(target_score, 7.0)
                    tag_flagged = True

            if tag_flagged:
                tap_issue_index += 1
                    
        scores.append(target_score)

        final_score = sum(scores) / len(scores) if scores else 10.0
        
        return EvaluationResult(
            domain=self.domain,
            score=round(final_score, 1),
            issues=issues,
            metadata={
                "has_viewport": viewport is not None,
                "small_font_tags": small_font_count,
                "nav_depth": max_depth,
                "interactive_elements_checked": len(interactive_tags),
                "has_cookie_banner": None
            }
        )
