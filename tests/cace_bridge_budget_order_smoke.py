#!/usr/bin/env python3
"""Ensure CACE bridge never touches deploy credentials or the CACE repo before budgeting."""
from pathlib import Path

root=Path(__file__).resolve().parents[1]
bridge=(root/'.github/workflows/external-free-runner-bridge.yml').read_text(encoding='utf-8')
ordered=[
    '      - name: Check out Expert Robot',
    '      - name: Enforce Avrea half-month budget',
    '      - name: Prepare deploy key',
    '      - name: Package current Expert Robot source',
    '      - name: Install request on isolated Cace-app bridge branch',
    '      - name: Await external free-runner evidence',
    '      - name: Upload external runner evidence',
    '      - name: Remove key material',
]
indices=[bridge.find(x) for x in ordered]
assert all(i>=0 for i in indices) and indices==sorted(indices), 'bridge budget must precede credentials and writes'
assert bridge.count('      - name: Enforce Avrea half-month budget')==1
assert '--reserve-minutes 30' in bridge
assert 'git@github.com:morganaspim/Cace-app.git' in bridge
assert 'runs-on: [self-hosted, cace, oci, aarch64]' in bridge
assert 'authority": "qualification-only"' in bridge
assert 'monetary_cost": "free"' in bridge
print('CACE bridge budget/order smoke: PASS')
