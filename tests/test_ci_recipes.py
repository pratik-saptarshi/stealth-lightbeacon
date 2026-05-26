from pathlib import Path


RECIPE_FILES = [
    Path("ci-recipes/github-actions/audit.yml"),
    Path("ci-recipes/gitlab/.gitlab-ci.yml"),
    Path("ci-recipes/bitbucket/bitbucket-pipelines.yml"),
]


def test_ci_recipe_templates_are_checked_in_and_env_driven():
    for recipe in RECIPE_FILES:
        assert recipe.exists(), recipe
        text = recipe.read_text(encoding="utf-8")
        assert "SLB_TARGET_URL" in text
        assert "SLB_AUTH_TOKEN" in text
        assert "SLB_AUDITS" in text
        assert "SLB_FAIL_ON_CRITICAL" in text
        assert "report.json" in text
        assert "report.html" in text
