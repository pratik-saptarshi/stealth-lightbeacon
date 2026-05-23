"""
generator.py — Unified Report Generator for HTML and JSON formats.
Renders responsive, professional diagnostic reports using Jinja2 templates.
"""

import os
import json
from typing import List, Dict, Any
from jinja2 import Environment, select_autoescape
from modules.base import EvaluationResult, Issue

class ReportGenerator:
    """
    Consolidates evaluation results and exports them to structured formats (JSON/HTML).
    """
    HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Drupal Evaluator - Audit Diagnostics Report</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Plus+Jakarta+Sans:wght@300;400;500;600;700&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg-dark: #0b0d17;
      --bg-card: rgba(17, 22, 39, 0.7);
      --border-card: rgba(255, 255, 255, 0.08);
      --primary: #4f46e5;
      --primary-hover: #4338ca;
      --primary-glow: rgba(79, 70, 229, 0.15);
      --accent: #06b6d4;
      --accent-glow: rgba(6, 182, 212, 0.15);
      
      --severity-critical: #ef4444;
      --severity-warning: #f59e0b;
      --severity-pass: #10b981;
      --severity-info: #3b82f6;
      
      --text-main: #f3f4f6;
      --text-muted: #9ca3af;
      --text-darker: #4b5563;
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    body {
      background-color: var(--bg-dark);
      color: var(--text-main);
      font-family: 'Plus Jakarta Sans', sans-serif;
      line-height: 1.6;
      background-image: 
        radial-gradient(circle at 10% 20%, rgba(79, 70, 229, 0.08) 0%, transparent 40%),
        radial-gradient(circle at 90% 80%, rgba(6, 182, 212, 0.06) 0%, transparent 45%);
      background-attachment: fixed;
      padding-bottom: 80px;
    }

    .container {
      max-width: 1200px;
      margin: 0 auto;
      padding: 40px 20px;
    }

    /* Header */
    header {
      margin-bottom: 40px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid var(--border-card);
      padding-bottom: 24px;
    }

    .logo-container h1 {
      font-family: 'Outfit', sans-serif;
      font-size: 2.2rem;
      font-weight: 800;
      letter-spacing: -0.5px;
      background: linear-gradient(135deg, #fff 30%, #a5b4fc 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }

    .logo-container p {
      color: var(--text-muted);
      font-size: 0.95rem;
      margin-top: 4px;
    }

    .badge-verdict {
      background: rgba(79, 70, 229, 0.12);
      border: 1px solid rgba(79, 70, 229, 0.4);
      color: #a5b4fc;
      padding: 8px 16px;
      border-radius: 100px;
      font-weight: 600;
      font-size: 0.9rem;
      letter-spacing: 0.5px;
      text-transform: uppercase;
    }

    /* Grid Layout */
    .dashboard-grid {
      display: grid;
      grid-template-columns: 2fr 1fr;
      gap: 30px;
      margin-bottom: 40px;
    }

    @media (max-width: 900px) {
      .dashboard-grid {
        grid-template-columns: 1fr;
      }
    }

    /* Cards */
    .card {
      background: var(--bg-card);
      border: 1px solid var(--border-card);
      border-radius: 16px;
      padding: 30px;
      backdrop-filter: blur(12px);
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
    }

    .card h2 {
      font-family: 'Outfit', sans-serif;
      font-size: 1.4rem;
      font-weight: 600;
      margin-bottom: 20px;
      border-left: 4px solid var(--primary);
      padding-left: 12px;
    }

    /* Overview Stats */
    .overview-content {
      display: flex;
      align-items: center;
      gap: 40px;
    }

    .score-circle {
      position: relative;
      width: 140px;
      height: 140px;
      border-radius: 50%;
      background: conic-gradient(var(--primary) {{ score_percent }}%, rgba(255, 255, 255, 0.05) {{ score_percent }}%);
      display: flex;
      justify-content: center;
      align-items: center;
      box-shadow: 0 0 20px var(--primary-glow);
    }

    .score-circle::after {
      content: '';
      position: absolute;
      width: 114px;
      height: 114px;
      border-radius: 50%;
      background: #0f111e;
    }

    .score-inner {
      position: relative;
      z-index: 10;
      text-align: center;
    }

    .score-value {
      font-family: 'Outfit', sans-serif;
      font-size: 2.2rem;
      font-weight: 800;
      color: #fff;
    }

    .score-max {
      font-size: 0.85rem;
      color: var(--text-muted);
    }

    .overview-text h3 {
      font-size: 1.15rem;
      color: #fff;
      margin-bottom: 8px;
    }

    .overview-text p {
      color: var(--text-muted);
      font-size: 0.95rem;
      max-width: 480px;
    }

    /* Scores Table */
    .scores-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
      gap: 15px;
      margin-top: 25px;
    }

    .score-card {
      background: rgba(255, 255, 255, 0.02);
      border: 1px solid var(--border-card);
      padding: 16px;
      border-radius: 10px;
      text-align: center;
    }

    .score-card-title {
      font-size: 0.8rem;
      color: var(--text-muted);
      margin-bottom: 6px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .score-card-value {
      font-family: 'Outfit', sans-serif;
      font-size: 1.3rem;
      font-weight: 700;
      color: #fff;
    }

    /* Details Table */
    .table-container {
      margin-top: 40px;
    }

    .domain-table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 15px;
    }

    .domain-table th, .domain-table td {
      padding: 14px 16px;
      text-align: left;
      border-bottom: 1px solid var(--border-card);
    }

    .domain-table th {
      font-family: 'Outfit', sans-serif;
      font-weight: 600;
      color: #fff;
      background: rgba(255, 255, 255, 0.02);
    }

    .domain-table tr:hover td {
      background: rgba(255, 255, 255, 0.01);
    }

    .score-indicator {
      font-weight: 700;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 0.9rem;
    }

    .score-high { color: var(--severity-pass); }
    .score-mid { color: var(--severity-warning); }
    .score-low { color: var(--severity-critical); }

    /* Finding Logs */
    .finding-list {
      margin-top: 40px;
      display: flex;
      flex-direction: column;
      gap: 15px;
    }

    .finding-card {
      background: var(--bg-card);
      border: 1px solid var(--border-card);
      border-radius: 12px;
      padding: 20px;
    }

    .finding-card-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 12px;
    }

    .finding-id-title {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .finding-id {
      font-family: 'Fira Code', monospace;
      font-size: 0.8rem;
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--border-card);
      padding: 4px 8px;
      border-radius: 4px;
      color: #fff;
    }

    .finding-title {
      font-size: 1.05rem;
      font-weight: 600;
      color: #fff;
    }

    .severity-badge {
      font-size: 0.75rem;
      font-weight: 700;
      padding: 4px 10px;
      border-radius: 100px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .sev-critical { background: rgba(239, 68, 68, 0.1); color: var(--severity-critical); border: 1px solid rgba(239, 68, 68, 0.2); }
    .sev-warning { background: rgba(245, 158, 11, 0.1); color: var(--severity-warning); border: 1px solid rgba(245, 158, 11, 0.2); }
    .sev-info { background: rgba(59, 130, 246, 0.1); color: var(--severity-info); border: 1px solid rgba(59, 130, 246, 0.2); }
    .sev-pass { background: rgba(16, 185, 129, 0.1); color: var(--severity-pass); border: 1px solid rgba(16, 185, 129, 0.2); }

    .finding-desc {
      color: var(--text-muted);
      font-size: 0.9rem;
      margin-bottom: 12px;
    }

    .finding-remedy {
      background: rgba(0, 0, 0, 0.2);
      border-radius: 6px;
      padding: 12px;
      font-size: 0.85rem;
      border-left: 3px solid var(--accent);
      color: var(--text-main);
    }

    .finding-remedy strong {
      color: var(--accent);
      font-size: 0.8rem;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      display: block;
      margin-bottom: 4px;
    }

    .finding-location {
      font-size: 0.8rem;
      color: var(--text-darker);
      margin-top: 6px;
      font-family: 'Fira Code', monospace;
    }

    footer {
      margin-top: 80px;
      text-align: center;
      color: var(--text-darker);
      font-size: 0.8rem;
      border-top: 1px solid var(--border-card);
      padding-top: 24px;
    }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="logo-container">
        <h1>Drupal Evaluator</h1>
        <p>Technical Site Audit Diagnostics & Scorecards</p>
      </div>
      <div class="badge-verdict">
        Audit Report
      </div>
    </header>

    <div class="dashboard-grid">
      <!-- Left: Score and Overview -->
      <div class="card">
        <h2>Audit Overview</h2>
        <div class="overview-content">
          <div class="score-circle">
            <div class="score-inner">
              <span class="score-value">{{ "%.1f" | format(average_score) }}</span>
              <span class="score-max">/10</span>
            </div>
          </div>
          <div class="overview-text">
            <h3>Audit Score Summary</h3>
            <p>
              Target site: <a href="{{ target_url }}" style="color: var(--accent); text-decoration: none;" target="_blank">{{ target_url }}</a><br>
              An automated, asynchronous audit of Technical SEO, PageSpeed Performance, Accessibility, and speculative AEO/GEO optimization metrics has concluded.
            </p>
          </div>
        </div>

        <div class="scores-grid">
          {% for domain in domains %}
          <div class="score-card">
            <div class="score-card-title">{{ domain.name }}</div>
            <div class="score-card-value">{{ "%.1f" | format(domain.score) }}</div>
          </div>
          {% endfor %}
        </div>
      </div>

      <!-- Right: Quick Metadata -->
      <div class="card">
        <h2>Execution Metadata</h2>
        <div style="font-size: 0.9rem; color: var(--text-muted); display: flex; flex-direction: column; gap: 10px; margin-top: 10px;">
          <div><strong>Target Page:</strong> {{ target_url }}</div>
          <div><strong>Total Gaps Flagged:</strong> {{ total_issues }}</div>
          <div><strong>Audit Engine Version:</strong> v1.0.0</div>
        </div>
      </div>
    </div>

    <!-- Domain Breakdown Table -->
    <div class="card table-container">
      <h2>Domain Breakdown</h2>
      <table class="domain-table">
        <thead>
          <tr>
            <th>Domain Evaluated</th>
            <th>Diagnostic Score</th>
            <th>Issues Flagged</th>
          </tr>
        </thead>
        <tbody>
          {% for domain in domains %}
          <tr>
            <td><strong>{{ domain.name }}</strong></td>
            <td>
              <span class="score-indicator {% if domain.score >= 8.0 %}score-high{% elif domain.score >= 5.0 %}score-mid{% else %}score-low{% endif %}">
                {{ "%.1f" | format(domain.score) }}/10.0
              </span>
            </td>
            <td>{{ domain.issues | length }} issues</td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>

    <!-- Issues Log -->
    <div class="finding-list">
      <h2>Diagnostic Gap & Recommendation Log</h2>
      {% for domain in domains %}
        {% for issue in domain.issues %}
        <div class="finding-card">
          <div class="finding-card-header">
            <div class="finding-id-title">
              <span class="finding-id">{{ issue.id }}</span>
              <span class="finding-title">{{ issue.message }}</span>
            </div>
            <span class="severity-badge {% if issue.severity == 'critical' %}sev-critical{% elif issue.severity == 'warning' %}sev-warning{% elif issue.severity == 'info' %}sev-info{% else %}sev-pass{% endif %}">
              {{ issue.severity }}
            </span>
          </div>
          <div class="finding-desc"><strong>Domain:</strong> {{ domain.name }}</div>
          {% if issue.remedy %}
          <div class="finding-remedy">
            <strong>Recommended Fix:</strong>
            {{ issue.remedy }}
          </div>
          {% endif %}
          {% if issue.location %}
          <div class="finding-location">
            Code/DOM Anchor: <code>{{ issue.location }}</code>
          </div>
          {% endif %}
        </div>
        {% endfor %}
      {% endfor %}
      {% if total_issues == 0 %}
      <div class="finding-card" style="text-align: center; color: var(--severity-pass);">
        ✔ All standard compliance filters passed! No diagnostic issues were flagged.
      </div>
      {% endif %}
    </div>

    <footer>
      Drupal Evaluator Diagnostics Report — Compiled Offline
    </footer>
  </div>
</body>
</html>
"""

    @classmethod
    def generate_report(cls, url: str, results: List[EvaluationResult], output_dir: str):
        """
        Generates JSON and Jinja2-rendered HTML reports.
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # Calculate scores
        avg_score = sum(r.score for r in results) / len(results) if results else 0.0
        total_issues = sum(len(r.issues) for r in results)
        
        # Prepare Jinja2 Variables
        domains_data = []
        for r in results:
            domain_dict = {
                "name": r.domain,
                "score": r.score,
                "issues": [
                    {
                        "id": issue.id,
                        "severity": issue.severity,
                        "message": issue.message,
                        "location": issue.location,
                        "remedy": issue.remedy
                    } for issue in r.issues
                ]
            }
            domains_data.append(domain_dict)
            
        # Render HTML with autoescape enabled
        env = Environment(autoescape=select_autoescape(['html', 'xml']))
        template = env.from_string(cls.HTML_TEMPLATE)
        html_content = template.render(
            target_url=url,
            average_score=avg_score,
            score_percent=int(avg_score * 10),
            total_issues=total_issues,
            domains=domains_data
        )
        
        html_path = os.path.join(output_dir, "report.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
