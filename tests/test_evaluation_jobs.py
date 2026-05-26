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
