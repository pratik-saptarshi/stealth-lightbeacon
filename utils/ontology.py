import os
import json
import hashlib
import asyncio
import re
import uuid
from datetime import datetime, timezone
from utils.vector import make_vector
from utils.crawl_diff import compare_audit_reports
from report.formats import normalize_report_payload

SERVICE_API_VERSION = "0.2.0"
DEFAULT_SERVICE_BASE_URL = "http://127.0.0.1:8000"

_ARTIFACT_FORMAT_MAP = {
    "json": {"name": "report.json", "media_type": "application/json"},
    "html": {"name": "report.html", "media_type": "text/html"},
    "llm": {"name": "report.md", "media_type": "text/markdown"},
    "geo-xml": {"name": "report.xml", "media_type": "application/xml"},
}
_ARTIFACT_ALIASES = {
    "both": ("json", "html"),
}

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
            "audit_findings": [],
            "evaluations": [],
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
        elif sql_upper.startswith("SELECT"):
            m = re.search(
                r"SELECT\s+(.*?)\s+FROM\s+(\w+)\s+WHERE\s+(\w+)\s*=\s*\?",
                sql,
                re.IGNORECASE | re.DOTALL,
            )
            if m:
                cols_str, table_name, where_col = m.groups()
                rows = [row for row in self.tables.get(table_name, []) if row.get(where_col) == params[0]]
                if not rows:
                    return MockQueryResult(None)
                cols = [col.strip() for col in cols_str.split(",")]
                if len(cols) == 1 and cols[0] == "*":
                    row = rows[0]
                    return MockQueryResult(tuple(row.get(key) for key in row.keys()))
                row = rows[0]
                return MockQueryResult(tuple(row.get(col) for col in cols))

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
        self._vector_buffer = []
        self._vector_flush_threshold = 25
        
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

    def _insert_vector_rows(self, rows: list[dict]) -> None:
        if not rows:
            return
        try:
            self.vector_store.insert(rows)
            return
        except Exception:
            for row in rows:
                try:
                    self.vector_store.insert([row])
                except Exception:
                    pass

    async def _queue_vector_row(self, row: dict, force: bool = False):
        self._vector_buffer.append(row)
        if force or len(self._vector_buffer) >= self._vector_flush_threshold:
            await self._flush_vector_buffer()

    async def _flush_vector_buffer(self):
        if not self._vector_buffer:
            return
        rows = self._vector_buffer
        self._vector_buffer = []
        self._insert_vector_rows(rows)

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
        self.duck_conn.execute("""
            CREATE TABLE IF NOT EXISTS evaluations (
                evaluation_id VARCHAR PRIMARY KEY,
                target_url VARCHAR,
                profile VARCHAR,
                output_formats_json VARCHAR,
                max_depth INTEGER,
                max_urls INTEGER,
                fail_on_critical BOOLEAN,
                budget_gate BOOLEAN,
                accepted_at VARCHAR,
                started_at VARCHAR,
                completed_at VARCHAR,
                status VARCHAR,
                stage VARCHAR,
                progress_percent INTEGER,
                message VARCHAR,
                exit_state VARCHAR,
                terminal BOOLEAN,
                request_json VARCHAR,
                result_json VARCHAR,
                artifacts_json VARCHAR
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
        await self._queue_vector_row(vector_row)

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
        await self._queue_vector_row(vector_row)

    async def finish_run(self, run_id: str, report_dict: dict, page_count: int, domain_count: int):
        report_payload = normalize_report_payload(report_dict)
        completed_at = datetime.now(timezone.utc).isoformat()
        
        async with self.db_lock:
            self.duck_conn.execute(
                "UPDATE audit_runs SET completed_at = ?, page_count = ?, domain_count = ?, report_json = ? WHERE run_id = ?",
                [completed_at, page_count, domain_count, json.dumps(report_payload), run_id]
            )
        await self._flush_vector_buffer()
        summary_text = f"Audit run finished for {report_payload.get('target_url', 'unknown')}. Pages: {page_count}. Domains: {domain_count}."
        vector = make_vector(summary_text, self.vector_dimensions)
        
        vector_row = {
            "id": f"run:{run_id}",
            "kind": "run",
            "label": report_payload.get('target_url', 'unknown'),
            "metadata": json.dumps(report_payload),
            "runId": run_id,
            "score": 10.0,
            "text": summary_text,
            "url": report_payload.get('target_url', 'unknown'),
            "vector": vector
        }
        self._insert_vector_rows([vector_row])

    def _normalize_output_formats(self, output_formats: list[str]) -> list[str]:
        normalized: list[str] = []
        for item in output_formats:
            key = str(item).strip().lower()
            if not key:
                continue
            expanded = _ARTIFACT_ALIASES.get(key, (key,))
            for fmt in expanded:
                if fmt in _ARTIFACT_FORMAT_MAP and fmt not in normalized:
                    normalized.append(fmt)
        if not normalized:
            raise ValueError("At least one supported output format is required")
        return normalized

    def _build_artifact_descriptors(
        self,
        evaluation_id: str,
        output_formats: list[str],
        base_url: str = DEFAULT_SERVICE_BASE_URL,
    ) -> list[dict]:
        root = base_url.rstrip("/")
        descriptors = []
        for fmt in self._normalize_output_formats(output_formats):
            spec = _ARTIFACT_FORMAT_MAP[fmt]
            descriptors.append(
                {
                    "name": spec["name"],
                    "kind": "report",
                    "mediaType": spec["media_type"],
                    "downloadUrl": f"{root}/evaluations/{evaluation_id}/artifacts/{spec['name']}",
                }
            )
        return descriptors

    def _load_evaluation_row(self, evaluation_id: str) -> dict:
        row = self.duck_conn.execute(
            """
            SELECT evaluation_id, target_url, profile, output_formats_json, max_depth, max_urls,
                   fail_on_critical, budget_gate, accepted_at, started_at, completed_at,
                   status, stage, progress_percent, message, exit_state, terminal,
                   request_json, result_json, artifacts_json
            FROM evaluations
            WHERE evaluation_id = ?
            """,
            [evaluation_id],
        ).fetchone()
        if not row:
            raise ValueError(f"Missing evaluation: {evaluation_id}")
        keys = [
            "evaluation_id",
            "target_url",
            "profile",
            "output_formats_json",
            "max_depth",
            "max_urls",
            "fail_on_critical",
            "budget_gate",
            "accepted_at",
            "started_at",
            "completed_at",
            "status",
            "stage",
            "progress_percent",
            "message",
            "exit_state",
            "terminal",
            "request_json",
            "result_json",
            "artifacts_json",
        ]
        return dict(zip(keys, row))

    def _row_to_status_payload(self, row: dict) -> dict:
        payload = {
            "evaluationId": row["evaluation_id"],
            "status": row["status"],
            "terminal": bool(row["terminal"]),
        }
        if row.get("stage"):
            payload["stage"] = row["stage"]
        if row.get("progress_percent") is not None:
            payload["progressPercent"] = int(row["progress_percent"])
        if row.get("message"):
            payload["message"] = row["message"]
        if row.get("exit_state"):
            payload["exitState"] = row["exit_state"]
        return payload

    def _row_to_result_payload(self, row: dict) -> dict:
        if not row.get("result_json"):
            raise ValueError(f"Missing terminal result for evaluation: {row['evaluation_id']}")
        result = json.loads(row["result_json"]) if isinstance(row["result_json"], str) else row["result_json"]
        return result

    def _derive_exit_state(self, report_payload: dict, fail_on_critical: bool, budget_gate: bool) -> str:
        severity_counts: dict[str, int] = {}
        for domain in report_payload.get("domains", []):
            for issue in domain.get("issues", []):
                severity = str(issue.get("severity", "")).lower()
                if severity:
                    severity_counts[severity] = severity_counts.get(severity, 0) + 1
        if budget_gate and float(report_payload.get("average_score", 0.0) or 0.0) < 8.0:
            return "budget_breach"
        if fail_on_critical and severity_counts.get("critical", 0) > 0:
            return "failure"
        return "success"

    async def create_evaluation(
        self,
        request: dict,
        evaluation_id: str | None = None,
        accepted_at: str | None = None,
    ) -> dict:
        evaluation_id = evaluation_id or f"eval_{uuid.uuid4().hex[:12]}"
        accepted_at = accepted_at or datetime.now(timezone.utc).isoformat()

        target = str(request.get("target") or "").strip()
        profile = str(request.get("profile") or "").strip()
        output_formats = request.get("outputFormats") or []
        if not target:
            raise ValueError("Evaluation target is required")
        if not profile:
            raise ValueError("Evaluation profile is required")
        if not isinstance(output_formats, list) or not output_formats:
            raise ValueError("At least one output format is required")

        normalized_formats = self._normalize_output_formats(output_formats)
        request_payload = {
            "target": target,
            "profile": profile,
            "outputFormats": normalized_formats,
            "maxDepth": int(request.get("maxDepth", 1) or 1),
            "maxUrls": int(request.get("maxUrls", 10) or 10),
            "failOnCritical": bool(request.get("failOnCritical", False)),
            "budgetGate": bool(request.get("budgetGate", False)),
        }
        async with self.db_lock:
            self.duck_conn.execute("DELETE FROM evaluations WHERE evaluation_id = ?", [evaluation_id])
            self.duck_conn.execute(
                """
                INSERT INTO evaluations (
                    evaluation_id, target_url, profile, output_formats_json, max_depth, max_urls,
                    fail_on_critical, budget_gate, accepted_at, started_at, completed_at, status,
                    stage, progress_percent, message, exit_state, terminal, request_json,
                    result_json, artifacts_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    evaluation_id,
                    target,
                    profile,
                    json.dumps(normalized_formats),
                    request_payload["maxDepth"],
                    request_payload["maxUrls"],
                    request_payload["failOnCritical"],
                    request_payload["budgetGate"],
                    accepted_at,
                    None,
                    None,
                    "queued",
                    "queued",
                    0,
                    "Evaluation accepted",
                    None,
                    False,
                    json.dumps(request_payload),
                    None,
                    None,
                ],
            )
        return {
            "evaluationId": evaluation_id,
            "status": "queued",
            "acceptedAt": accepted_at,
        }

    async def update_evaluation_status(
        self,
        evaluation_id: str,
        status: str,
        stage: str | None = None,
        progress_percent: int | None = None,
        message: str | None = None,
        exit_state: str | None = None,
        terminal: bool | None = None,
        started_at: str | None = None,
        completed_at: str | None = None,
    ) -> dict:
        row = self._load_evaluation_row(evaluation_id)
        started_at = started_at or row.get("started_at")
        if started_at is None and status in {"running", "processing"}:
            started_at = datetime.now(timezone.utc).isoformat()
        completed_at = completed_at or row.get("completed_at")
        if terminal and completed_at is None:
            completed_at = datetime.now(timezone.utc).isoformat()
        normalized_progress = None if progress_percent is None else max(0, min(100, int(progress_percent)))
        normalized_terminal = bool(row.get("terminal")) if terminal is None else bool(terminal)
        async with self.db_lock:
            self.duck_conn.execute(
                """
                UPDATE evaluations
                SET status = ?, stage = ?, progress_percent = ?, message = ?, exit_state = ?,
                    terminal = ?, started_at = ?, completed_at = ?
                WHERE evaluation_id = ?
                """,
                [
                    status,
                    stage if stage is not None else row.get("stage"),
                    normalized_progress if normalized_progress is not None else row.get("progress_percent"),
                    message if message is not None else row.get("message"),
                    exit_state if exit_state is not None else row.get("exit_state"),
                    normalized_terminal,
                    started_at,
                    completed_at,
                    evaluation_id,
                ],
            )
        return self._row_to_status_payload(self._load_evaluation_row(evaluation_id))

    async def get_evaluation_status(self, evaluation_id: str) -> dict:
        return self._row_to_status_payload(self._load_evaluation_row(evaluation_id))

    async def complete_evaluation(
        self,
        evaluation_id: str,
        report_dict: dict,
        base_url: str = DEFAULT_SERVICE_BASE_URL,
        completed_at: str | None = None,
    ) -> dict:
        row = self._load_evaluation_row(evaluation_id)
        report_payload = normalize_report_payload(report_dict)
        output_formats = json.loads(row["output_formats_json"]) if row.get("output_formats_json") else ["json"]
        artifacts = self._build_artifact_descriptors(evaluation_id, output_formats, base_url=base_url)
        started_at = row.get("started_at") or row.get("accepted_at")
        completed_at = completed_at or datetime.now(timezone.utc).isoformat()
        severity_counts: dict[str, int] = {}
        findings = []
        for domain in report_payload["domains"]:
            for issue in domain["issues"]:
                severity = str(issue.get("severity", "")).lower()
                if severity:
                    severity_counts[severity] = severity_counts.get(severity, 0) + 1
                findings.append(
                    {
                        "ruleId": issue.get("id", ""),
                        "title": issue.get("message", ""),
                        "severity": issue.get("severity", ""),
                        "status": "resolved" if issue.get("severity") == "pass" else "open",
                        "description": " | ".join(
                            part for part in [issue.get("location", ""), issue.get("remedy", "")] if part
                        ),
                    }
                )
        result_payload = {
            "evaluationId": evaluation_id,
            "status": "completed",
            "summary": report_payload,
            "severityCounts": severity_counts,
            "findings": findings,
            "startedAt": started_at,
            "completedAt": completed_at,
        }
        exit_state = self._derive_exit_state(
            report_payload,
            bool(row.get("fail_on_critical")),
            bool(row.get("budget_gate")),
        )
        async with self.db_lock:
            self.duck_conn.execute(
                """
                UPDATE evaluations
                SET status = ?, stage = ?, progress_percent = ?, message = ?, exit_state = ?,
                    terminal = ?, completed_at = ?, result_json = ?, artifacts_json = ?, started_at = ?
                WHERE evaluation_id = ?
                """,
                [
                    "completed",
                    "completed",
                    100,
                    "Evaluation completed",
                    exit_state,
                    True,
                    completed_at,
                    json.dumps(result_payload),
                    json.dumps(artifacts),
                    started_at,
                    evaluation_id,
                ],
            )
        return result_payload

    async def get_evaluation_result(self, evaluation_id: str) -> dict:
        return self._row_to_result_payload(self._load_evaluation_row(evaluation_id))

    async def get_evaluation_artifacts(self, evaluation_id: str, base_url: str = DEFAULT_SERVICE_BASE_URL) -> list[dict]:
        row = self._load_evaluation_row(evaluation_id)
        if row.get("artifacts_json"):
            return json.loads(row["artifacts_json"])
        if not row.get("terminal"):
            return []
        output_formats = json.loads(row["output_formats_json"]) if row.get("output_formats_json") else ["json"]
        artifacts = self._build_artifact_descriptors(evaluation_id, output_formats, base_url=base_url)
        async with self.db_lock:
            self.duck_conn.execute(
                "UPDATE evaluations SET artifacts_json = ? WHERE evaluation_id = ?",
                [json.dumps(artifacts), evaluation_id],
            )
        return artifacts

    async def get_run_report(self, run_id: str) -> dict:
        row = self.duck_conn.execute("SELECT report_json FROM audit_runs WHERE run_id = ?", [run_id]).fetchone()
        if not row or row[0] is None:
            raise ValueError(f"Missing audit run: {run_id}")
        raw = row[0]
        report = json.loads(raw) if isinstance(raw, str) else raw
        return normalize_report_payload(report)

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
        if self._vector_buffer:
            rows = self._vector_buffer
            self._vector_buffer = []
            self._insert_vector_rows(rows)
        try:
            self.duck_conn.close()
        except Exception:
            pass
