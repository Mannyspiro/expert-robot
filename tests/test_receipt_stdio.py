"""Interleave two live local CLI hosts and interrupt an outstanding clarification."""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class StdioIsolationTests(unittest.TestCase):
    def test_interleaved_conversations_and_interruption(self):
        with ExitStack() as stack:
            def start():
                proc = stack.enter_context(subprocess.Popen(
                    [sys.executable, "scripts/merlin/ask_receipt.py", "--stdio"],
                    cwd=ROOT, env={**os.environ, "PYTHONPATH":str(ROOT/"python")},
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True))
                stack.callback(proc.kill)
                return proc

            def turn(proc, question):
                proc.stdin.write(question + "\n")
                proc.stdin.flush()
                return json.loads(proc.stdout.readline())

            first, second = start(), start()
            self.assertEqual(turn(first, "How many main shard tests ran?")["disposition"], "clarify_run")
            self.assertEqual(turn(second, "What was the submission status?")["disposition"], "clarify_run")
            a = turn(first, "44151750942")
            b = turn(second, "44174486449")
            self.assertEqual((a["value"],a["citation"]["pointer"]), (136,"/tests/tests"))
            self.assertEqual((b["value"],b["citation"]["pointer"]), ("pending_review","/demo/submission_status"))
            turn(first, "How many main shard tests ran?")
            replacement = turn(first, "For the learning run, what was the submission status?")
            self.assertEqual(replacement["value"], "pending_review")
            stale_reply = turn(first, "44151750942")
            self.assertEqual(stale_reply["disposition"], "clarify_field")
            self.assertNotIn("citation", stale_reply)
            for proc in (first,second):
                proc.stdin.close()
                self.assertEqual(proc.wait(timeout=5), 0)
