import os
import shutil
import pytest
import asyncio
from utils.ontology import OntologyStore

@pytest.mark.asyncio
async def test_ontology_store_flow():
    test_dir = ".data/test_store"
    # Ensure test directory is clean
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
        
    store = OntologyStore(root_dir=test_dir, vector_dimensions=16)
    
    try:
        # 1. Begin a run
        run_id = "test-run-123"
        await store.begin_run(
            run_id=run_id,
            target_url="https://example.com",
            started_at="2026-05-25T00:00:00Z",
            options={"crawl_depth": 1}
        )
        
        # 2. Record a page
        html_content = "<html><title>Diagnostic Test Page</title><body>This is a page about web accessibility issues.</body></html>"
        await store.record_page(
            run_id=run_id,
            page_url="https://example.com/a11y",
            html_content=html_content,
            status_code=200,
            response_time_ms=120,
            headers={"Content-Type": "text/html"}
        )
        
        # 3. Record a finding
        await store.record_finding(
            run_id=run_id,
            page_url="https://example.com/a11y",
            domain_id="Accessibility",
            issue_id="R-A11Y-ALT-MISSING",
            severity="critical",
            message="Image is missing an alt text description.",
            location="img.logo",
            remedy="Add alt attribute.",
            metadata={"tag": "img"}
        )
        
        # 4. Finish the run
        report = {"targetUrl": "https://example.com", "brokenPages": {}}
        await store.finish_run(run_id, report, page_count=1, domain_count=1)
        
        # 5. Check DuckDB values
        runs = store.duck_conn.execute("SELECT count(*) FROM audit_runs").fetchone()[0]
        pages = store.duck_conn.execute("SELECT count(*) FROM audit_pages").fetchone()[0]
        findings = store.duck_conn.execute("SELECT count(*) FROM audit_findings").fetchone()[0]
        
        assert runs == 1
        assert pages == 1
        assert findings == 1
        
        # 6. Check semantic search
        search_results = store.search("web accessibility", limit=2)
        assert len(search_results) > 0
        assert any("accessibility" in res["text"] for res in search_results)
        
    finally:
        store.close()
        # Clean up
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)
