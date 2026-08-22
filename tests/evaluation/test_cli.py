from app.evaluation import EvalStatus, OverallStatus
from app.evaluation.__main__ import main
from tests.evaluation.test_runner import _report, _result


def test_cli_pass_exit_code_and_filters(tmp_path):
    output = tmp_path / "reports"
    code = main(
        [
            "--offline",
            "--domain", "knowledge",
            "--case", "knowledge.year-question",
            "--output", str(output),
        ]
    )
    assert code == 0
    assert (output / "benchmark-report.json").is_file()
    assert (output / "benchmark-report.md").is_file()


def test_cli_does_not_update_baseline_without_explicit_flag(tmp_path):
    baseline = tmp_path / "baseline.json"
    baseline.write_text("sentinel", encoding="utf-8")
    assert main(["--output", str(tmp_path / "reports")]) == 0
    assert baseline.read_text(encoding="utf-8") == "sentinel"


def test_cli_explicit_baseline_update_and_compare(tmp_path):
    baseline = tmp_path / "baseline.json"
    output = tmp_path / "reports"
    assert main(["--output", str(output), "--update-baseline", str(baseline)]) == 0
    assert baseline.is_file()
    compared = tmp_path / "compared"
    assert main([
        "--output", str(compared), "--compare-baseline", str(baseline)
    ]) == 0
    assert "UNCHANGED" in (compared / "benchmark-report.md").read_text(encoding="utf-8")


def test_cli_returns_nonzero_for_hard_failure(tmp_path, monkeypatch):
    failed = _report(
        (
            _result(
                "case",
                "planning.runtime_completion",
                EvalStatus.FAIL,
                False,
                hard=True,
            ),
        ),
        status=OverallStatus.FAIL,
        hard_failures=("case / planning.runtime_completion",),
    )

    class FailingRunner:
        def run(self, **kwargs):
            return failed

    monkeypatch.setattr("app.evaluation.__main__.BenchmarkRunner", FailingRunner)
    assert main(["--output", str(tmp_path / "reports")]) == 2
