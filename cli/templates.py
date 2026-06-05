"""CI template generator for AIGuard."""
from __future__ import annotations

REPORT_DIR = ".aiguard/reports"


def github_template(project: str) -> str:
    return f"""name: AIGuard Evaluation

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  aiguard:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install AIGuard
        run: pip install aiguard-safety
      - name: Run evaluation
        env:
          OPENAI_API_KEY: ${{{{ secrets.OPENAI_API_KEY }}}}
        run: aiguard evaluate --project {project} --mode quick
      - name: Upload AIGuard report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: aiguard-report
          path: {REPORT_DIR}/
          if-no-files-found: warn
          retention-days: 30
"""


def gitlab_template(project: str) -> str:
    return f"""aiguard_eval:
  image: python:3.11
  stage: test
  script:
    - pip install aiguard-safety
    - aiguard evaluate --project {project} --mode quick
  rules:
    - if: $CI_PIPELINE_SOURCE == 'merge_request_event'
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
  artifacts:
    when: always
    expire_in: 30 days
    paths:
      - {REPORT_DIR}/
  variables:
    OPENAI_API_KEY: "$OPENAI_API_KEY"
"""
