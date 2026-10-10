#!/usr/bin/env python3
"""No-network regression checks for bounded GitHub-based research worker."""
import importlib.util
from pathlib import Path
from unittest.mock import patch
path=Path(__file__).resolve().parents[1]/"server"/"research"/"worker.py"
spec=importlib.util.spec_from_file_location("research_worker",path)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
assert module.approved_ref("refs/heads/main")=="refs/heads/main"
for name in ("refs/heads/../bad","refs/heads/a//b","refs/heads/foo.lock","main"):
    try:module.approved_ref(name)
    except ValueError:pass
    else:raise AssertionError("unapproved ref was accepted: "+name)
with patch.object(module,"run",return_value="git@github.com:Mannyspiro/expert-robot.git"):
    module.assert_remote(Path("/tmp/example"),"git@github.com:Mannyspiro/expert-robot.git")
    try:module.assert_remote(Path("/tmp/example"),"ssh://git@127.0.0.1:2222/Mannyspiro/expert-robot.git")
    except ValueError:pass
    else:raise AssertionError("unapproved Forgejo remote was accepted")
service=(path.parent/"expert-robot-research.service").read_text()
installer=(path.parent/"install.sh").read_text()
assert "--image ${WORKER_IMAGE}" in service
assert "git@github.com:Mannyspiro/expert-robot.git" in service
assert "ssh://git@127.0.0.1:2222/" not in service
assert "/etc/expert-robot-github/worker.env" in service
assert "/etc/expert-robot-github/worker.env" in installer
print("GitHub worker safety smoke: PASS")
