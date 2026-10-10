#!/usr/bin/env python3
"""Synthetic GitHub pagination safety tests; no network, credentials or Avrea minutes."""
import importlib.util
from pathlib import Path
import time
from unittest.mock import patch

root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location(
    'budget',root/'scripts/check_avrea_halfmonth_budget.py')
budget=importlib.util.module_from_spec(spec)
spec.loader.exec_module(budget)

records=[{'id':k,'status':'completed'} for k in range(205)]
def fake(url,token,timeout=8):
    assert token == 'synthetic'
    assert 0<timeout<=8
    page=int(url.split('page=')[-1])
    return {'total_count':len(records),'workflow_runs':
            records[(page-1)*100:page*100]}
with patch.object(budget,'request_json',side_effect=fake) as spy:
    out=budget.list_pages('https://example.invalid/actions/runs',
                          'synthetic','workflow_runs',deadline=time.monotonic()+10)
    assert out == records
    assert spy.call_count==3

# A stalled or truncated enumeration cannot approve budget.
with patch.object(budget,'request_json',side_effect=fake):
    try:budget.list_pages('https://example.invalid/actions/runs',
                          'synthetic','workflow_runs',max_pages=2,
                          deadline=time.monotonic()+10)
    except RuntimeError:pass
    else:raise AssertionError('partial pagination was accepted')

def duplicate(url,token,timeout=8):
    page=int(url.split('page=')[-1])
    data=records[(page-1)*100:page*100]
    if page==2:data=[{'id':r['id']-1} for r in data]
    return {'total_count':205,'workflow_runs':data}
with patch.object(budget,'request_json',side_effect=duplicate):
    try:budget.list_pages('https://example.invalid/actions/runs',
                          'synthetic','workflow_runs',deadline=time.monotonic()+10)
    except ValueError:pass
    else:raise AssertionError('duplicate GitHub job/run IDs were accepted')

with patch.object(budget,'request_json',return_value={'total_count':3,'workflow_runs':[{'id':1}]}):
    try:budget.list_pages('https://example.invalid/actions/runs',
                          'synthetic','workflow_runs',deadline=time.monotonic()+10)
    except ValueError:pass
    else:raise AssertionError('incomplete one-page response was accepted')

with patch.object(budget,'request_json',side_effect=AssertionError('network attempted')):
    try:budget.list_pages('https://example.invalid/actions/runs',
                          'synthetic','workflow_runs',deadline=time.monotonic()-1)
    except RuntimeError:pass
    else:raise AssertionError('expired budget deadline did not block')

import json
policy=json.loads((root/'config/avrea_half_month_budget.json').read_text())
for workflow,minutes in [('avrea-offline-receipt-qualification.yml',5),
                          ('cace-biochemical-diffusion.yml',10)]:
    assert workflow in policy['avrea_workflow_files']
    assert policy['estimated_max_run_minutes'][workflow] == minutes
assert policy['fail_closed_on_usage_error'] is True
print('Avrea bounded paged usage and workflow accounting: PASS')
