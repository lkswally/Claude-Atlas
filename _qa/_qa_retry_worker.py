"""Worker process spawned by _qa/bloque-qa-retry-ceiling.py (test_13).

Records N real QA-fail attempts via the real production QARetryState for
the same task_id, from a separate OS process, against a disposable
project_root. Not a test file itself.
"""
import sys

sys.path.insert(0, sys.argv[1])  # tools/ dir, so `qa_retry_state` imports
from qa_retry_state import QARetryState

project_root = sys.argv[2]
task_id = sys.argv[3]
n_attempts = int(sys.argv[4])

s = QARetryState(project_root)
for i in range(n_attempts):
    s.record_qa_attempt(task_id, "fail", reason=f"worker fixture attempt {i}")
