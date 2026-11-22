#!/usr/bin/env python3
"""Check Studio's shipped inline JavaScript syntax using a native Node parser.

This is a syntactic test, not a rendered-browser, camera, microphone or
accessibility acceptance run. No application code executes.
"""
from html.parser import HTMLParser
from pathlib import Path
import shutil
import subprocess
import tempfile


class ScriptCollector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.in_script = False
        self.parts = []
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            if self.in_script or any(key == "src" for key, _ in attrs):
                raise ValueError("expected one self-contained inline Studio script")
            self.in_script = True
            self.parts = []

    def handle_data(self, data):
        if self.in_script:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == "script":
            if not self.in_script:
                raise ValueError("unmatched script end")
            self.scripts.append("".join(self.parts))
            self.in_script = False
            self.parts = []


def main():
    node = shutil.which("node")
    if not node:
        raise RuntimeError("node is required for Studio syntax acceptance")
    html = Path(__file__).resolve().parents[1] / "portable/merlin_studio/web/index.html"
    collector = ScriptCollector()
    collector.feed(html.read_text(encoding="utf-8"))
    collector.close()
    if collector.in_script or len(collector.scripts) != 1:
        raise ValueError("Studio must contain exactly one complete inline script")
    with tempfile.TemporaryDirectory(prefix="merlin-js-") as directory:
        script = Path(directory) / "studio.js"
        script.write_text(collector.scripts[0], encoding="utf-8")
        result = subprocess.run([node, "--check", str(script)], capture_output=True,
                                text=True, check=False, timeout=10)
        if result.returncode:
            raise RuntimeError("Studio JavaScript parse failed: " + result.stderr[-3000:])
    print("PASS: Studio inline JS parses; no script was executed or browser acceptance claimed.")


if __name__ == "__main__":
    main()
