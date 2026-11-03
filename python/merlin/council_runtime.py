"""Local-only model execution for the Merlin council.

Each role's opening call is isolated from other role outputs. Optional second
rounds expose the completed opening transcript for cross-examination. No remote
provider, tool use, promotion, or merge authority is available here.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from typing import Any
from urllib.request import Request, urlopen

from .app_config import MAX_COUNCIL_RESPONSE if False else None
