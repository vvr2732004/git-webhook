import os


def ci_failure_probe() -> str:
    return "This file exists only to trigger a Ruff failure in CI."
