"""
config.py — Shared configuration and constants for Stealth Lightbeacon.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─── PageSpeed Insights API ───────────────────────────────────────────────────
PAGESPEED_API_KEY = os.getenv("PAGESPEED_API_KEY", "")
PAGESPEED_API_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

# ─── HTTP Request Settings ────────────────────────────────────────────────────
REQUEST_TIMEOUT = 15       # seconds
REQUEST_HEADERS = {
    "User-Agent": (
        "StealthLightbeacon/1.1.3 (+https://github.com/pratik-saptarshi/stealth-lightbeacon) "
        "Mozilla/5.0 (compatible; StealthLightbeaconBot/1.1.3)"
    )
}

# ─── Scoring Thresholds ────────────────────────────────────────────────────────
# Core Web Vitals (Google thresholds)
LCP_GOOD = 2500       # ms
LCP_POOR = 4000       # ms
INP_GOOD = 200        # ms
INP_POOR = 500        # ms
CLS_GOOD = 0.1
CLS_POOR = 0.25
TTFB_GOOD = 800       # ms
TTFB_POOR = 1800      # ms

# ─── Issue Severity Levels ─────────────────────────────────────────────────────
SEVERITY_CRITICAL = "critical"
SEVERITY_WARNING  = "warning"
SEVERITY_PASS     = "pass"
SEVERITY_INFO     = "info"

# ─── AEO ──────────────────────────────────────────────────────────────────────
DIRECT_ANSWER_MAX_WORDS = 50   # max words for a "direct answer" paragraph

# ─── GEO ──────────────────────────────────────────────────────────────────────
KEYWORD_STUFFING_DENSITY = 0.04   # 4% single-keyword density triggers a warning

# ─── Report ───────────────────────────────────────────────────────────────────
REPORT_OUTPUT_DIR = "reports"
