"""Called by Claude during a task when a fact is missing:
    python ask_client.py "How many integrations do you support today?"
Uses GEO_CLIENT and GEO_TASK_ID, which the runner sets for each task."""
import os
import sys

import comms
from common import client_cfg

question = " ".join(sys.argv[1:]).strip()
if not question or "GEO_CLIENT" not in os.environ:
    sys.exit('usage (inside a GEO task): python ask_client.py "your question"')
comms.ask(client_cfg(os.environ["GEO_CLIENT"]), int(os.environ["GEO_TASK_ID"]), question)
print("Question queued for the client. Stop working on this task now and summarize your progress; "
      "the task will resume in this same session when they answer.")
