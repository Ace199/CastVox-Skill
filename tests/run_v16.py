"""Separated M1/V1.6 evidence; all non-loopback socket connections are denied."""
import argparse
import importlib.util
import io
import json
import platform
import socket
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.run_m1 import RecordedResult


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("docs/V1.6_Test_Results.json"))
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("provider_config_tests", Path(__file__).resolve().parents[1] / "web/tests/test_provider_config.py")
    provider_tests = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(provider_tests)
    groups = {"M1_original": ["tests.unit.test_m1", "tests.integration.test_cli"],
              "V1.6_core": ["tests.unit.test_v16", "tests.unit.test_model_redaction"],
              "V1.6_HTTP": ["tests.integration.test_v16_http"], "provider_config_existing": [provider_tests]}
    summary = {"python": platform.python_version(), "os": platform.system(), "paid_api_calls": 0,
               "network_policy": "non-loopback connections blocked; CLI subprocesses block all connections", "groups": {}}
    original_connect = socket.socket.connect
    def loopback_only(sock, address):
        if not isinstance(address, tuple) or address[0] != "127.0.0.1":
            raise AssertionError("EXTERNAL_NETWORK_FORBIDDEN")
        return original_connect(sock, address)
    with patch.object(socket.socket, "connect", loopback_only):
        for label, names in groups.items():
            suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(item) if isinstance(item, str)
                                       else unittest.defaultTestLoader.loadTestsFromModule(item) for item in names)
            logs = io.StringIO()
            start = time.monotonic()
            result = unittest.TextTestRunner(stream=logs, verbosity=2, resultclass=RecordedResult).run(suite)
            group = {"total": result.testsRun, "passed": sum(r["result"] == "PASS" for r in result.records),
                     "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
                     "duration_seconds": round(time.monotonic() - start, 3), "tests": result.records}
            summary["groups"][label] = group
            print(json.dumps({"group": label, **{k: v for k, v in group.items() if k != "tests"}}, ensure_ascii=False))
            for test, traceback in result.failures + result.errors:
                print(test.id() + ": " + traceback.strip().splitlines()[-1])
    summary["total"] = sum(g["total"] for g in summary["groups"].values())
    summary["passed"] = sum(g["passed"] for g in summary["groups"].values())
    args.output.parent.mkdir(exist_ok=True, parents=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if summary["total"] == summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
