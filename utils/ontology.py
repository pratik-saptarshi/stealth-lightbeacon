import os
import json
import hashlib
import asyncio
import re
from datetime import datetime, timezone
from utils.vector import make_vector
from utils.crawl_diff import compare_audit_reports

# Try lazy loading duckdb
DUCKDB_AVAILABLE = False
try:
    import duckdb
    DUCKDB_AVAILABLE = True
except ImportError:
    pass

# Try lazy loading lancedb
LANCEDB_AVAILABLE = False
try:
    import lancedb
    LANCEDB_AVAILABLE = True
except ImportError:
    pass

class MockQueryResult:
    def __init__(self, fetchone_val):
        self.val = fetchone_val

    def fetchone(self):
        return self.val

class MockDuckDbConnection:
    """Mock DuckDB connection using in-memory Python structures for environment independence."""
    def __init__(self):
        self.tables = {
            "audit_runs": [],
            "audit_pages": [],
            "audit_findings": []
        }

    def execute(self, sql, params=None):
        if params is None:
            params = []
            
        sql_upper = sql.upper().strip()
        
        # 1. CREATE TABLE
        if "CREATE TABLE" in sql_upper:
            pass
            
        # 2. DELETE FROM
        elif "DELETE FROM" in sql_upper:
            m = re.search(r"DELETE FROM\s+(\w+)\s+WHERE\s+(\w+)\s*=\s*\?", sql, re.IGNORECASE)
            if m:
                table_name, col_name = m.groups()
                val = params[0]
                if table_name in self.tables:
                    self.tables[table_name] = [row for row in self.tables[table_name] if row.get(col_name) != val]
                    
        # 3. INSERT INTO
        elif "INSERT INTO" in sql_upper:
            m = re.search(r"INSERT INTO\s+(\w+)\s*\((.*?)\)\s*VALUES\s*\((.*?)\)", sql, re.IGNORECASE | re.DOTALL)
            if m:
                table_name, cols_str, _ = m.groups()
                cols = [c.strip() for c in cols_str.split(",")]
                row = dict(zip(cols, params))
                if table_name in self.tables:
                    self.tables[table_name].append(row)
                    
        # 4. UPDATE
        elif "UPDATE" in sql_upper:
            m = re.search(r"UPDATE\s+(\w+)\s+SET\s+(.*?)\s+WHERE\s+(\w+)\s*=\s*\?", sql, re.IGNORECASE | re.DOTALL)
            if m:
                table_name, set_str, cond_col = m.groups()
                set_parts = [p.strip().split("=")[0].strip() for p in set_str.split(",")]
                val_cond = params[-1]
                set_vals = params[:-1]
                if table_name in self.tables:
                    for row in self.tables[table_name]:
                        if row.get(cond_col) == val_cond:
                            for col, val in zip(set_parts, set_vals):
                                row[col] = val
                                
        # 5. SELECT COUNT(*)
        elif "SELECT COUNT(*)" in sql_upper or "SELECT COUNT(1)" in sql_upper:
            m = re.search(r"FROM\s+(\w+)", sql, re.IGNORECASE)
            if m:
                table_name = m.group(1)
                count = len(self.tables.get(table_name, []))
                return MockQueryResult((count,))
                
        # 6. SELECT 1 (health check)
        elif "SELECT 1" in sql_upper:
            return MockQueryResult((1,))
        elif "SELECT REPORT_JSON" in sql_upper:
            m = re.search(r"WHERE\s+RUN_ID\s*=\s*\?", sql, re.IGNORECASE)
            if m:
                run_id = params[0]
                rows = [row for row in self.tables.get("audit_runs", []) if row.get("run_id") == run_id]
                if rows:
                    return MockQueryResult((rows[0].get("report_json"),))
            
        return self

    def fetchone(self):
        return None

    def close(self):
        pass

class FallbackVectorStore:
    """Pure-Python fallback vector store performing in-memory cosine similarity searches."""
    def __init__(self):
        self.rows = []

    def insert(self, rows):
        for row in rows:
            self.rows.append(dict(row))

    def search(self, query_vector, limit=10):
        results = []
        for row in self.rows:
            vec = row.get("vector")
            if not vec or len(vec) != len(query_vector):
                continue
            similarity = sum(a * b for a, b in zip(query_vector, vec))
            results.append((similarity, row))
        
        results.sort(key=lambda x: x[0], reverse=True)
        return [res[1] for res in results[:limit]]

class LanceDbStore:
    """Wrapper around LanceDB providing robust storage and search."""
    def __init__(self, db_path, table_name):
        self.db = lancedb.connect(db_path)
        self.table_name = table_name
        self.table = None
        self._sync_table()

    def _sync_table(self):
        try:
            self.table = self.db.open_table(self.table_name)
        except Exception:
            self.table = None

    def insert(self, rows):
        if self.table is None:
            self.table = self.db.create_table(self.table_name, data=rows, mode="overwrite")
        else:
            self.table.add(rows)

    def search(self, query_vector, limit=10):
        self._sync_table()
        if self.table is None:
            return []
        try:
            return self.table.search(query_vector).limit(limit).to_list()
        except Exception:
            return []

class OntologyStore:
    """Coordinates relational storage (DuckDB / Memory Mock) and semantic index (LanceDB / Memory)."""
    def __init__(self, root_dir=".data", vector_dimensions=64):
        self.root_dir = root_dir
        os.makedirs(self.root_dir, exist_ok=True)
        
        self.duckdb_path = os.path.join(self.root_dir, "stealth_audit.duckdb")
        self.lancedb_uri = os.path.join(self.root_dir, "lancedb")
        self.vector_dimensions = vector_dimensions
        
        # Enforce single-writer locks for DuckDB
        self.db_lock = asyncio.Lock()
        
        # Initialize DuckDB or Mock
        if DUCKDB_AVAILABLE:
            try:
                import duckdb
                self.duck_conn = duckdb.connect(self.duckdb_path)
            except Exception:
                self.duck_conn = MockDuckDbConnection()
        else:
            self.duck_conn = MockDuckDbConnection()
            
        self._initialize_duckdb_schema()
        
        # Initialize LanceDB / Fallback
        if LANCEDB_AVAILABLE:
            try:
                self.vector_store = LanceDbStore(self.lancedb_uri, "ontology_memory")
            except Exception:
                self.vector_store = FallbackVectorStore()
        else:
            self.vector_store = FallbackVectorStore()

    def _initialize_duckdb_schema(self):
        self.duck_conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_runs (
                run_id VARCHAR PRIMARY KEY,
                target_url VARCHAR,
                started_at VARCHAR,
                completed_at VARCHAR,
                created_at VARCHAR,
                page_count INTEGER,
                domain_count INTEGER,
                report_json VARCHAR,
                options_json VARCHAR
            )
        """)
        self.duck_conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_pages (
                run_id VARCHAR,
                page_url VARCHAR,
                status INTEGER,
                response_time_ms INTEGER,
                page_hash VARCHAR,
                title VARCHAR,
                headers_json VARCHAR,
                metadata_json VARCHAR
            )
        """)
        self.duck_conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_findings (
                run_id VARCHAR,
                page_url VARCHAR,
                domain_id VARCHAR,
                issue_id VARCHAR,
                severity VARCHAR,
                message VARCHAR,
                location VARCHAR,
                remedy VARCHAR,
                metadata_json VARCHAR
            )
        """)

    async def begin_run(self, run_id: str, target_url: str, started_at: str, options: dict):
        async with self.db_lock:
            self.duck_conn.execute("DELETE FROM audit_runs WHERE run_id = ?", [run_id])
            self.duck_conn.execute(
                "INSERT INTO audit_runs (run_id, target_url, started_at, created_at, options_json) VALUES (?, ?, ?, ?, ?)",
                [run_id, target_url, started_at, started_at, json.dumps(options)]
            )

    async def record_page(self, run_id: str, page_url: str, html_content: str, status_code: int = 200, response_time_ms: int = 0, headers: dict = None):
        if headers is None:
            headers = {}
            
        page_hash = hashlib.sha256(html_content.encode("utf-8")).hexdigest()
        
        # Extract simple title
        title = page_url
        match = re.search(r"<title>(.*?)</title>", html_content, re.IGNORECASE | re.DOTALL)
        if match:
            title = match.group(1).strip()
            
        metadata = {
            "headers": headers,
            "pageHash": page_hash,
            "responseTimeMs": response_time_ms,
            "status": status_code
        }
        
        async with self.db_lock:
            self.duck_conn.execute(
                "INSERT INTO audit_pages (run_id, page_url, status, response_time_ms, page_hash, title, headers_json, metadata_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [run_id, page_url, status_code, response_time_ms, page_hash, title, json.dumps(headers), json.dumps(metadata)]
            )
            
        # Strip HTML for vector representation
        stripped_text = re.sub(r"<[^>]+>", " ", html_content)
        stripped_text = " ".join(stripped_text.split())[:2000]
        
        vector = make_vector(stripped_text, self.vector_dimensions)
        
        vector_row = {
            "id": f"page:{hashlib.sha256(page_url.encode('utf-8')).hexdigest()[:16]}",
            "kind": "page",
            "label": title,
            "metadata": json.dumps(metadata),
            "runId": run_id,
            "score": float(max(0, 10 - response_time_ms / 500)),
            "text": stripped_text,
            "url": page_url,
            "vector": vector
        }
        self.vector_store.insert([vector_row])

    async def record_finding(self, run_id: str, page_url: str, domain_id: str, issue_id: str, severity: str, message: str, location: str = "", remedy: str = "", metadata: dict = None):
        if metadata is None:
            metadata = {}
            
        async with self.db_lock:
            self.duck_conn.execute(
                "INSERT INTO audit_findings (run_id, page_url, domain_id, issue_id, severity, message, location, remedy, metadata_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [run_id, page_url, domain_id, issue_id, severity, message, location, remedy, json.dumps(metadata)]
            )
            
        finding_text = f"Issue in {domain_id}: {message}. Location: {location}. Remedy: {remedy}"
        vector = make_vector(finding_text, self.vector_dimensions)
        
        vector_row = {
            "id": f"finding:{hashlib.sha256((page_url + issue_id).encode('utf-8')).hexdigest()[:16]}",
            "kind": "finding",
            "label": f"{domain_id} - {issue_id}",
            "metadata": json.dumps(metadata),
            "runId": run_id,
            "score": 0.0,
            "text": finding_text,
            "url": page_url,
            "vector": vector
        }
        self.vector_store.insert([vector_row])

    async def finish_run(self, run_id: str, report_dict: dict, page_count: int, domain_count: int):
        normalized_target_url = report_dict.get("target_url") or report_dict.get("targetUrl", "unknown")
        completed_at = datetime.now(timezone.utc).isoformat()
        
        async with self.db_lock:
            self.duck_conn.execute(
                "UPDATE audit_runs SET completed_at = ?, page_count = ?, domain_count = ?, report_json = ? WHERE run_id = ?",
                [completed_at, page_count, domain_count, json.dumps(report_dict), run_id]
            )
            
        summary_text = f"Audit run finished for {normalized_target_url}. Pages: {page_count}. Domains: {domain_count}."
        vector = make_vector(summary_text, self.vector_dimensions)
        
        vector_row = {
            "id": f"run:{run_id}",
            "kind": "run",
            "label": normalized_target_url,
            "metadata": json.dumps(report_dict),
            "runId": run_id,
            "score": 10.0,
            "text": summary_text,
            "url": normalized_target_url,
            "vector": vector
        }
        self.vector_store.insert([vector_row])

    async def get_run_report(self, run_id: str) -> dict:
        row = self.duck_conn.execute("SELECT report_json FROM audit_runs WHERE run_id = ?", [run_id]).fetchone()
        if not row or row[0] is None:
            raise ValueError(f"Missing audit run: {run_id}")
        raw = row[0]
        return json.loads(raw) if isinstance(raw, str) else raw

    async def diff_runs(self, previous_run_id: str, current_run_id: str) -> dict:
        previous = await self.get_run_report(previous_run_id)
        current = await self.get_run_report(current_run_id)
        return compare_audit_reports(previous, current)

    def search(self, query: str, limit: int = 10) -> list:
        """Performs a semantic search on LanceDB / Memory vector store."""
        query_vector = make_vector(query, self.vector_dimensions)
        results = self.vector_store.search(query_vector, limit)
        
        formatted_results = []
        for row in results:
            formatted_results.append({
                "id": row.get("id"),
                "kind": row.get("kind"),
                "label": row.get("label"),
                "runId": row.get("runId"),
                "text": row.get("text"),
                "url": row.get("url"),
                "score": row.get("score"),
                "metadata": json.loads(row.get("metadata")) if isinstance(row.get("metadata"), str) else row.get("metadata")
            })
        return formatted_results

    def health(self) -> dict:
        """Returns readiness checks for DuckDB and the Vector Store."""
        try:
            self.duck_conn.execute("SELECT 1")
            duck_ok = True
        except Exception:
            duck_ok = False
            
        return {
            "duckDbReady": duck_ok,
            "lanceDbReady": LANCEDB_AVAILABLE and not isinstance(self.vector_store, FallbackVectorStore)
        }

    def close(self):
        try:
            self.duck_conn.close()
        except Exception:
            pass
