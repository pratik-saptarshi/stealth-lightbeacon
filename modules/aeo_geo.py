"""
aeo_geo.py — Experimental Answer Engine (AEO) and Generative Engine (GEO) optimizer.
Evaluates Q&A outline structures, snippet readability, E-E-A-T author schemas,
authoritative citations, publication recency, and keyword stuffing densities.
"""

import re
import json
from collections import Counter
from typing import List, Dict, Any, Optional
from modules.html_parser import HtmlParser
import config
from modules.base import BaseEvaluator, EvaluationResult, Issue

class AeoGeoEvaluator(BaseEvaluator):
    """
    Evaluator for AEO (Answer Engine Optimization) and GEO (Generative Engine Optimization).
    Designated as [EXPERIMENTAL].
    """
    def __init__(self):
        self.domain = "AEO & GEO Optimization"

    async def evaluate(self, html: str, url: str, client: Optional[Any] = None, allow_private: bool = False) -> EvaluationResult:
        """
        Runs speculative and NLP algorithms to verify AEO and GEO optimization properties.
        """
        import asyncio
        soup = await asyncio.to_thread(HtmlParser, html)
        issues = []
        scores = []
        readiness_components = {}
        json_ld_payloads = [script.string or "" for script in soup.find_all("script", type="application/ld+json")]
        
        # Strip script/style tags for text analysis after preserving JSON-LD references.
        for style in soup(["style"]):
            style.decompose()
        for script in soup.find_all("script"):
            script.decompose()
        body_text = soup.get_text()

        # ─── 1. AEO: Direct Answer & Q&A Detection ───────────────────────
        paragraphs = soup.find_all("p")
        direct_answer_pass = False
        qa_detected = False
        
        # Look for Q&A outline (headings containing standard question starters followed by paragraphs)
        question_pattern = re.compile(r"\b(what|how|why|who|where|when|can|is|are|should)\b", re.IGNORECASE)
        headings = soup.find_all(re.compile(r"^h[2-4]$"))
        
        for heading in headings:
            heading_text = heading.get_text().strip()
            if question_pattern.search(heading_text):
                qa_detected = True
                # Find the next sibling paragraph
                sibling = heading.find_next()
                if sibling and sibling.name == "p":
                    words = sibling.get_text().strip().split()
                    word_count = len(words)
                    
                    # Target featured snippet paragraph is between 30 and 55 words
                    if 8 <= word_count <= config.DIRECT_ANSWER_MAX_WORDS:
                        direct_answer_pass = True
                        break
                        
        if not qa_detected:
            issues.append(Issue(
                id="R-AEO-QA-NONE",
                severity=config.SEVERITY_WARNING,
                message="No clear Q&A outline or question headings detected in sub-headers.",
                location="Headers (H2-H4)",
                remedy="Structure dynamic content with direct questions (e.g. 'What is X?') to match natural language voice search patterns."
            ))
            scores.append(6.0)
        elif not direct_answer_pass:
            issues.append(Issue(
                id="R-AEO-SNIPPET-LEN",
                severity=config.SEVERITY_WARNING,
                message="Q&A paragraph length is suboptimal for direct AI engine extraction.",
                location="Q&A Sibling Paragraphs",
                remedy=f"Keep target answer summaries concise (between 30 and {config.DIRECT_ANSWER_MAX_WORDS} words) directly following a question heading."
            ))
            scores.append(7.0)
        else:
            scores.append(10.0)
        readiness_components["answer_clarity"] = scores[-1]

        # ─── 1b. Heading Hierarchy Readiness ───────────────────────────
        heading_scores = [10.0]
        headings = soup.find_all(re.compile(r"^h[1-6]$"))
        if not headings:
            issues.append(Issue(
                id="R-AEO-HEADINGS-MISS",
                severity=config.SEVERITY_WARNING,
                message="No visible heading structure was detected for answer hierarchy.",
                location="Headers (H1-H6)",
                remedy="Use semantic headings to separate topics and answer blocks."
            ))
            heading_scores = [6.0]
        else:
            prev_level = None
            for heading in headings:
                level = int(heading.name[1])
                if prev_level is not None and level > prev_level + 1:
                    issues.append(Issue(
                        id="R-AEO-HEAD-SKIP",
                        severity=config.SEVERITY_WARNING,
                        message=f"Heading hierarchy skips from <h{prev_level}> to <{heading.name}>.",
                        location="Headers (H1-H6)",
                        remedy="Keep heading levels sequential to help answer extraction systems follow structure."
                    ))
                    heading_scores.append(6.0)
                    break
                prev_level = level
        scores.append(sum(heading_scores) / len(heading_scores))
        readiness_components["heading_hierarchy"] = scores[-1]

        # ─── 2. GEO: Authoritative Outbound Citations ───────────────────
        links = soup.find_all("a", href=True)
        outbound_citations = 0
        authority_citations = 0
        
        for link in links:
            href = link.get("href", "")
            if href.startswith("http"):
                outbound_citations += 1
                # Check for high authority top-level domains or nodes
                if any(ext in href.lower() for ext in [".edu", ".gov", ".org", "wikipedia.org", "arxiv.org"]):
                    authority_citations += 1
                    
        if outbound_citations == 0:
            issues.append(Issue(
                id="R-GEO-CIT-NONE",
                severity=config.SEVERITY_WARNING,
                message="No outbound citation links detected. Content is isolated.",
                location="Entire DOM",
                remedy="Link to authoritative sources, studies, or secondary research to build verification signals."
            ))
            scores.append(6.0)
        elif authority_citations == 0:
            issues.append(Issue(
                id="R-GEO-CIT-LOW",
                severity=config.SEVERITY_WARNING,
                message="Outbound citations lack high-authority reference anchors (no .edu, .gov, or academic references).",
                location="Outbound <a> tags",
                remedy="Reference studies or regulatory portals to verify speculative claims."
            ))
            scores.append(8.0)
        else:
            scores.append(10.0)
        readiness_components["source_quality"] = scores[-1]

        # ─── 3. GEO: Author E-E-A-T schemas & Recency ────────────────────
        has_author_details = False
        has_recency = False
        author_schema_required = len(json_ld_payloads) == 0
        structured_schema_found = False
        
        for script_payload in json_ld_payloads:
            try:
                ld_json = json.loads(script_payload)

                def schema_requires_author(obj):
                    if isinstance(obj, dict):
                        schema_type = obj.get("@type")
                        if isinstance(schema_type, str) and schema_type in {"Article", "BlogPosting", "NewsArticle", "FAQPage", "HowTo"}:
                            return True
                        if isinstance(schema_type, list) and any(item in {"Article", "BlogPosting", "NewsArticle", "FAQPage", "HowTo"} for item in schema_type):
                            return True
                        if schema_type:
                            return True
                        return any(schema_requires_author(v) for v in obj.values())
                    if isinstance(obj, list):
                        return any(schema_requires_author(item) for item in obj)
                    return False

                def has_target_structured_data(obj):
                    if isinstance(obj, dict):
                        schema_type = obj.get("@type")
                        if isinstance(schema_type, str) and schema_type in {"Article", "FAQPage", "HowTo", "BlogPosting", "NewsArticle"}:
                            return True
                        if isinstance(schema_type, list) and any(item in {"Article", "FAQPage", "HowTo", "BlogPosting", "NewsArticle"} for item in schema_type):
                            return True
                        return any(has_target_structured_data(v) for v in obj.values())
                    if isinstance(obj, list):
                        return any(has_target_structured_data(item) for item in obj)
                    return False
                
                # Check for author profile within Article or WebPage
                def check_author(obj):
                    if isinstance(obj, dict):
                        if "author" in obj:
                            author = obj["author"]
                            if isinstance(author, dict) and ("name" in author or "jobTitle" in author or "sameAs" in author):
                                return True
                        for k, v in obj.items():
                            if check_author(v):
                                return True
                    elif isinstance(obj, list):
                        for item in obj:
                            if check_author(item):
                                return True
                    return False
                    
                # Check for publication dates
                def check_dates(obj):
                    if isinstance(obj, dict):
                        if "datePublished" in obj or "dateModified" in obj:
                            return True
                        for k, v in obj.items():
                            if check_dates(v):
                                return True
                    elif isinstance(obj, list):
                        for item in obj:
                            if check_dates(item):
                                return True
                    return False
                    
                if check_author(ld_json):
                    has_author_details = True
                if check_dates(ld_json):
                    has_recency = True
                if schema_requires_author(ld_json):
                    author_schema_required = True
                if has_target_structured_data(ld_json):
                    structured_schema_found = True
            except Exception:
                pass

        if len(json_ld_payloads) and not structured_schema_found:
            issues.append(Issue(
                id="R-AEO-LD-STRUCT",
                severity=config.SEVERITY_WARNING,
                message="Structured data is present but does not advertise answer-oriented schema types.",
                location="JSON-LD script blocks",
                remedy="Prefer Article, FAQPage, or HowTo schema to make the page easier for answer engines to classify."
            ))
            scores.append(7.0)
        elif len(json_ld_payloads):
            scores.append(10.0)

        if author_schema_required and not has_author_details:
            issues.append(Issue(
                id="R-GEO-EEAT-AUTHOR",
                severity=config.SEVERITY_WARNING,
                message="Author profile credentials or E-E-A-T schemas missing from structured data.",
                location="JSON-LD script blocks",
                remedy="Configure author schema properties (including name, affiliation, and profile sameAs links) in Schema.org module settings."
            ))
            scores.append(7.0)
        else:
            scores.append(10.0)
            
        if not has_recency:
            issues.append(Issue(
                id="R-GEO-EEAT-RECENCY",
                severity=config.SEVERITY_WARNING,
                message="No temporal modification or publication dates (dateModified/datePublished) found in schemas.",
                location="JSON-LD script blocks",
                remedy="Ensure Drupal's Node schemas include the dateModified token to supply recency indicators."
            ))
            scores.append(8.0)
        else:
            scores.append(10.0)
        readiness_components["structured_data"] = scores[-1]

        # ─── 4. GEO: Keyword Stuffing Densities ──────────────────────────
        # Simple token clean-up and word frequencies
        words = re.findall(r"\b\w{4,15}\b", body_text.lower())
        total_words = len(words)
        
        stuffing_detected = False
        if total_words >= 20:
            word_counts = Counter(words)
            # Remove common grammatical stop words
            stops = {"with", "this", "that", "from", "they", "have", "were", "their", "there", "about", "which"}
            for stop in stops:
                if stop in word_counts:
                    del word_counts[stop]
                    
            most_common = word_counts.most_common(3)
            for word, count in most_common:
                density = count / total_words
                if count >= 4 and density > config.KEYWORD_STUFFING_DENSITY:
                    stuffing_detected = True
                    issues.append(Issue(
                        id="R-GEO-STUFFING-WARN",
                        severity=config.SEVERITY_WARNING,
                        message=f"Possible keyword stuffing warning: single word '{word}' has a density of {density*100:.1f}%. Config limit is {config.KEYWORD_STUFFING_DENSITY*100:.1f}%.",
                        location="Entire body text",
                        remedy="Ensure natural language flow and avoid repeating key target terms mechanically."
                    ))
                    scores.append(6.0)
                    break
                    
        if not stuffing_detected:
            scores.append(10.0)
        readiness_components["content_naturalness"] = scores[-1]

        final_score = sum(scores) / len(scores) if scores else 10.0
        
        return EvaluationResult(
            domain=self.domain,
            score=round(final_score, 1),
            issues=issues,
            metadata={
                "outbound_citations": outbound_citations,
                "authority_citations": authority_citations,
                "qa_outline_found": qa_detected,
                "eeat_author_found": has_author_details,
                "keyword_stuffing_alert": stuffing_detected,
                "readiness_components": readiness_components
            }
        )
