"""
accessibility.py — Static accessibility evaluator. Assesses HTML pages against WCAG 2.2 AA rules,
including heading hierarchies, image alt quality, ARIA attributes, and labeled form elements.
"""

import re
from typing import Any, List, Optional
from modules.html_parser import HtmlParser
import config
from modules.base import BaseEvaluator, EvaluationResult, Issue

class AccessibilityEvaluator(BaseEvaluator):
    """
    Evaluator for static website accessibility (WCAG 2.2 AA guidelines).
    """
    def __init__(self):
        self.domain = "Accessibility (WCAG 2.2 AA)"

    async def evaluate(self, html: str, url: str, client: Optional[Any] = None, allow_private: bool = False) -> EvaluationResult:
        """
        Executes accessibility audits on static HTML elements.
        """
        soup = HtmlParser(html)
        issues = []
        scores = []

        # ─── 1. Image Alt Text Audit (WCAG 1.1.1 Non-text Content) ───────
        images = soup.find_all("img")
        img_scores = []
        
        for idx, img in enumerate(images):
            src = img.get("src", f"image-{idx}")
            if "alt" not in img.attrs:
                issues.append(Issue(
                    id=f"R-A11Y-ALT-MISS-{idx}",
                    severity=config.SEVERITY_CRITICAL,
                    message=f"Image is missing an alt attribute: {src}",
                    location=str(img)[:100],
                    remedy="Always add an 'alt' attribute. Use descriptive alt text for informative images or an empty alt (alt=\"\") for decorative images."
                ))
                img_scores.append(2.0)
            else:
                alt_text = (img.get("alt") or "").strip()
                # Empty alt is valid for decorative images
                if not alt_text:
                    img_scores.append(10.0)
                    continue
                    
                # Check for generic filename alt texts
                filename_pattern = r"\.(png|jpg|jpeg|gif|webp|svg)$"
                if re.search(filename_pattern, alt_text, re.IGNORECASE) or alt_text.lower() in ["image", "img", "photo", "picture"]:
                    issues.append(Issue(
                        id=f"R-A11Y-ALT-BAD-{idx}",
                        severity=config.SEVERITY_WARNING,
                        message=f"Image alt text is uninformative or a file name: '{alt_text}' for src: {src}",
                        location=str(img)[:100],
                        remedy="Provide clear, concise descriptions instead of filenames or generic words like 'image'."
                    ))
                    img_scores.append(6.0)
                else:
                    img_scores.append(10.0)
                    
        if images:
            scores.append(sum(img_scores) / len(img_scores))
        else:
            scores.append(10.0)  # Perfect pass if no images exist

        # ─── 2. Heading Structure Audit (WCAG 1.3.1 Info and Relationships) 
        headings = soup.find_all(re.compile(r"^h[1-6]$"))
        h_scores = []
        
        h1_tags = soup.find_all("h1")
        if not h1_tags:
            issues.append(Issue(
                id="R-A11Y-H1-MISS",
                severity=config.SEVERITY_WARNING,
                message="Page is missing a main h1 heading tag.",
                location="Entire DOM",
                remedy="Ensure every page has exactly one H1 tag defining the primary topic."
            ))
            h_scores.append(4.0)
        elif len(h1_tags) > 1:
            issues.append(Issue(
                id="R-A11Y-H1-MULTIPLE",
                severity=config.SEVERITY_WARNING,
                message=f"Page contains multiple ({len(h1_tags)}) h1 tags, which breaks outline semantics.",
                location="Multiple <h1> tags",
                remedy="Combine sections under a single main H1 or change lower headings to H2 tags."
            ))
            h_scores.append(6.0)
        else:
            h_scores.append(10.0)

        # Check for skipped heading levels (e.g., H1 directly followed by H3 or H4)
        prev_level = None
        for idx, heading in enumerate(headings):
            level = int(heading.name[1])
            if prev_level is not None:
                if level > prev_level + 1:
                    issues.append(Issue(
                        id=f"R-A11Y-HEAD-SKIP-{idx}",
                        severity=config.SEVERITY_WARNING,
                        message=f"Skipped heading level from <{heading.name}> after <h{prev_level}>.",
                        location=str(heading)[:100],
                        remedy="Do not skip heading levels (e.g., transition from H1 to H2, not H1 to H3)."
                    ))
                    h_scores.append(6.0)
                else:
                    h_scores.append(10.0)
            prev_level = level
            
        if headings:
            scores.append(sum(h_scores) / len(h_scores))

        # ─── 3. ARIA & Empty Interactive Elements (WCAG 4.1.2 Name, Role, Value)
        # Empty links and buttons
        interactive_tags = soup.find_all(["a", "button"])
        ia_scores = []
        
        for idx, tag in enumerate(interactive_tags):
            # Check if interactive element has visible text or accessible labels
            text_content = tag.get_text().strip()
            aria_label = tag.get("aria-label", "").strip()
            aria_labelledby = tag.get("aria-labelledby", "").strip()
            
            # Skip links that only wrap images (alt text will provide accessible label)
            if tag.name == "a" and tag.find("img"):
                ia_scores.append(10.0)
                continue
                
            if not text_content and not aria_label and not aria_labelledby:
                issues.append(Issue(
                    id=f"R-A11Y-IA-EMPTY-{idx}",
                    severity=config.SEVERITY_CRITICAL,
                    message=f"Interactive element <{tag.name}> is empty and has no accessible name or aria-label.",
                    location=str(tag)[:100],
                    remedy="Provide clear inner text or set an explicit 'aria-label' attribute to explain the action to screen readers."
                ))
                ia_scores.append(2.0)
            else:
                ia_scores.append(10.0)
                
        if interactive_tags:
            scores.append(sum(ia_scores) / len(ia_scores))
        else:
            scores.append(10.0)

        # ─── 4. Form Accessibility Audit (WCAG 3.3.2 Labels or Instructions) ───
        forms = soup.find_all("form")
        form_scores = []
        
        for f_idx, form in enumerate(forms):
            inputs = form.find_all(["input", "textarea", "select"])
            has_submit = False
            
            for i_idx, inp in enumerate(inputs):
                inp_type = inp.get("type", "").lower()
                inp_id = inp.get("id", "").strip()
                
                # Check for form submit trigger
                if inp_type in ["submit", "image"] or inp.name == "button":
                    has_submit = True
                    continue
                    
                # Skip hidden inputs
                if inp_type == "hidden":
                    continue
                    
                # Check if input has an associated label
                label_by_id = soup.find("label", attrs={"for": inp_id}) if inp_id else None
                label_parent = inp.find_parent("label")
                aria_lbl = inp.get("aria-label", "").strip()
                aria_lbl_by = inp.get("aria-labelledby", "").strip()
                
                if not label_by_id and not label_parent and not aria_lbl and not aria_lbl_by:
                    issues.append(Issue(
                        id=f"R-A11Y-FORM-LABEL-{f_idx}-{i_idx}",
                        severity=config.SEVERITY_WARNING,
                        message=f"Form input '{inp.get('name', 'unnamed')}' has no associated label or aria-label.",
                        location=str(inp)[:100],
                        remedy="Bind a <label for=\"...\"> to the input ID, wrap it in a <label> tag, or supply an 'aria-label'."
                    ))
                    form_scores.append(6.0)
                else:
                    form_scores.append(10.0)
                    
            if inputs and not has_submit:
                issues.append(Issue(
                    id=f"R-A11Y-FORM-SUBMIT-{f_idx}",
                    severity=config.SEVERITY_WARNING,
                    message=f"Form #{f_idx} has no clear submit button or input[type=submit].",
                    location=str(form)[:100],
                    remedy="Add an explicit submit button (<button type=\"submit\">) inside the form."
                ))
                form_scores.append(6.0)
                
            if inputs:
                scores.append(sum(form_scores) / len(form_scores))
                
        final_score = sum(scores) / len(scores) if scores else 10.0
        
        return EvaluationResult(
            domain=self.domain,
            score=round(final_score, 1),
            issues=issues,
            metadata={
                "images_checked": len(images),
                "headings_checked": len(headings),
                "interactive_elements": len(interactive_tags),
                "forms_checked": len(forms)
            }
        )
