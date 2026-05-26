import time

from companion.jobs import EvaluationJobManager, JobExecutionOutcome


def sample_request():
    return {
        "target": "https://example.com",
        "profile": "baseline",
        "outputFormats": ["json"],
        "maxDepth": 2,
        "maxUrls": 25,
        "failOnCritical": False,
        "budgetGate": False,
    }


def test_job_manager_transitions_from_accepted_to_terminal_status():
    def fake_executor(request, evaluation_id, output_dir):
        time.sleep(0.05)
        return JobExecutionOutcome(
            status="success",
            exit_state="success",
            message="Evaluation complete.",
            result_payload={"target_url": request.target, "domains": []},
            artifacts=[],
        )

    manager = EvaluationJobManager(executor=fake_executor)
    accepted = manager.submit(sample_request())

    initial = manager.get_status(accepted["evaluationId"])
    assert initial["terminal"] is False
    assert initial["status"] in {"accepted", "running"}

    deadline = time.time() + 2
    terminal = None
    while time.time() < deadline:
        current = manager.get_status(accepted["evaluationId"])
        if current["terminal"]:
            terminal = current
            break
        time.sleep(0.02)

    assert terminal is not None
    assert terminal["status"] == "success"
    assert terminal["exitState"] == "success"
    assert terminal["progressPercent"] == 100


def test_job_manager_exposes_terminal_result_payload():
    def fake_executor(request, evaluation_id, output_dir):
        return JobExecutionOutcome(
            status="success",
            exit_state="success",
            message="Evaluation complete.",
            result_payload={
                "target_url": request.target,
                "average_score": 91.5,
                "total_issues": 2,
                "domains": [
                    {
                        "name": "Technical SEO",
                        "score": 9.0,
                        "issues": [
                            {
                                "id": "seo-title",
                                "severity": "warning",
                                "message": "Title is too short.",
                                "location": "/",
                                "remedy": "Expand the title.",
                            }
                        ],
                        "metadata": {},
                    }
                ],
            },
            artifacts=[],
        )

    manager = EvaluationJobManager(executor=fake_executor)
    accepted = manager.submit(sample_request())

    deadline = time.time() + 2
    while time.time() < deadline:
        status = manager.get_status(accepted["evaluationId"])
        if status["terminal"]:
            break
        time.sleep(0.02)

    result = manager.get_result(accepted["evaluationId"])

    assert result["evaluationId"] == accepted["evaluationId"]
    assert result["status"] == "success"
    assert result["summary"]["score"] == 91.5
    assert result["severityCounts"]["warning"] == 1
    assert result["findings"][0]["ruleId"] == "seo-title"
    assert result["findings"][0]["severity"] == "warning"
