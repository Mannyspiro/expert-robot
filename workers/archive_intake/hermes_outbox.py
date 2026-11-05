#!/usr/bin/env python3
"""Durable Hermes-compatible outbox with lease, retry and acknowledgement lifecycle."""
from __future__ import annotations
import argparse, hashlib, json, sqlite3, uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Protocol
from canonical_registry import connect, initialize

def now(): return datetime.now(timezone.utc)
def enqueue(database,event):
    if not event.get("event_id") or not event.get("event_type"): raise ValueError("event_id and event_type required")
    payload=json.dumps(event,sort_keys=True,separators=(",",":"))
    with connect(database) as db:
        db.execute("INSERT OR IGNORE INTO hermes_outbox(event_id,event_json,state,created_at) VALUES(?,?,?,?)",
          (event["event_id"],payload,"pending",now().isoformat()))
        row=db.execute("SELECT event_json FROM hermes_outbox WHERE event_id=?",(event["event_id"],)).fetchone()
        if row["event_json"]!=payload: raise ValueError("event_id collision with different payload")
    return {"event_id":event["event_id"],"state":"pending"}

def claim(database,worker,lease_seconds=60):
    if not worker or lease_seconds<1 or lease_seconds>3600: raise ValueError("invalid worker or lease duration")
    until=(now()+timedelta(seconds=lease_seconds)).isoformat()
    with connect(database) as db:
        db.execute("BEGIN IMMEDIATE")
        row=db.execute("""SELECT event_id,event_json FROM hermes_outbox
          WHERE state='pending' OR (state='leased' AND lease_until<?)
          ORDER BY created_at LIMIT 1""",(now().isoformat(),)).fetchone()
        if not row: return None
        db.execute("""UPDATE hermes_outbox SET state='leased',lease_owner=?,lease_until=?,attempts=attempts+1
          WHERE event_id=?""",(worker,until,row["event_id"]))
        return {"event_id":row["event_id"],"event":json.loads(row["event_json"]),
                "lease_owner":worker,"lease_until":until}

def acknowledge(database,event_id,worker,ack):
    if ack.get("event_id")!=event_id or ack.get("status")!="accepted":
        raise ValueError("acknowledgement must accept the exact event_id")
    ack["ack_sha256"]=hashlib.sha256(json.dumps(ack,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    with connect(database) as db:
        row=db.execute("SELECT state,lease_owner FROM hermes_outbox WHERE event_id=?",(event_id,)).fetchone()
        if not row: raise ValueError("unknown event")
        if row["state"]=="acked": return {"event_id":event_id,"state":"acked","idempotent":True}
        if row["state"]!="leased" or row["lease_owner"]!=worker: raise ValueError("worker does not own active event lease")
        db.execute("""UPDATE hermes_outbox SET state='acked',acknowledged_at=?,acknowledgement_json=?,
          lease_owner=NULL,lease_until=NULL WHERE event_id=?""",(now().isoformat(),json.dumps(ack,sort_keys=True),event_id))
    return {"event_id":event_id,"state":"acked","ack_sha256":ack["ack_sha256"]}

class HermesTransport(Protocol):
    def send(self,event: dict) -> dict: ...

def deliver_once(database,worker,transport):
    lease=claim(database,worker)
    if lease is None: return {"state":"empty"}
    try:
        ack=transport.send(lease["event"])
        return acknowledge(database,lease["event_id"],worker,ack)
    except Exception as exc:
        retry(database,lease["event_id"],worker,exc)
        return {"event_id":lease["event_id"],"state":"pending","delivery_error":str(exc)[:500]}

def retry(database,event_id,worker,error):
    with connect(database) as db:
        row=db.execute("SELECT state,lease_owner FROM hermes_outbox WHERE event_id=?",(event_id,)).fetchone()
        if not row or row["state"]!="leased" or row["lease_owner"]!=worker: raise ValueError("active lease required")
        db.execute("UPDATE hermes_outbox SET state='pending',lease_owner=NULL,lease_until=NULL WHERE event_id=?",(event_id,))
    return {"event_id":event_id,"state":"pending","last_error":str(error)[:500]}

def main():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest="cmd",required=True)
    q=sub.add_parser("enqueue"); q.add_argument("event",type=Path); q.add_argument("--database",default="data/merlin.sqlite3")
    c=sub.add_parser("claim"); c.add_argument("--worker",required=True); c.add_argument("--database",default="data/merlin.sqlite3")
    a=sub.add_parser("ack"); a.add_argument("event_id"); a.add_argument("ack",type=Path); a.add_argument("--worker",required=True); a.add_argument("--database",default="data/merlin.sqlite3")
    r=sub.add_parser("retry"); r.add_argument("event_id"); r.add_argument("--worker",required=True); r.add_argument("--error",required=True); r.add_argument("--database",default="data/merlin.sqlite3")
    args=p.parse_args(); initialize(args.database)
    if args.cmd=="enqueue": result=enqueue(args.database,json.loads(args.event.read_text()))
    elif args.cmd=="claim": result=claim(args.database,args.worker)
    elif args.cmd=="ack": result=acknowledge(args.database,args.event_id,args.worker,json.loads(args.ack.read_text()))
    else: result=retry(args.database,args.event_id,args.worker,args.error)
    print(json.dumps(result,indent=2))
if __name__=="__main__": main()
