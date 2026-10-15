"""Run the real offline suite and optionally save compact machine-readable evidence."""
import argparse
import io
import json
import platform
import sys
import time
import unittest
from pathlib import Path


class RecordedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.records.append({"test": test.id(), "result": "PASS"})

    def addError(self, test, err):
        super().addError(test, err)
        self.records.append({"test": test.id(), "result": "ERROR", "exception_type": err[0].__name__})

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.records.append({"test": test.id(), "result": "FAIL", "exception_type": err[0].__name__})

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.records.append({"test": test.id(), "result": "NOT RUN"})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    suite = unittest.defaultTestLoader.discover(str(root / "tests"), top_level_dir=str(root))
    logs = io.StringIO()
    start = time.monotonic()
    result = unittest.TextTestRunner(stream=logs, verbosity=2, resultclass=RecordedResult).run(suite)
    summary = {"milestone": "M1", "python": platform.python_version(), "os": platform.system(),
               "total": result.testsRun, "passed": sum(r["result"] == "PASS" for r in result.records),
               "failures": len(result.failures), "errors": len(result.errors), "not_run": len(result.skipped),
               "duration_seconds": round(time.monotonic() - start, 3), "tests": result.records}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "tests"}, ensure_ascii=False))
    if not result.wasSuccessful():
        print(logs.getvalue(), file=sys.stderr)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
