"""PII-free local command interface. Not a network service."""
import argparse
import json
from .workflow import Case, Stage
from .store import CaseStore

def main(argv=None):
    parser=argparse.ArgumentParser(description="Wilborn operations prototype (synthetic data only)")
    parser.add_argument("--db",default="wilborn-demo.sqlite3")
    sub=parser.add_subparsers(dest="command",required=True)
    create=sub.add_parser("create")
    create.add_argument("service",choices=["document_signing","insurance_quote","workshop","general"])
    advance=sub.add_parser("advance")
    advance.add_argument("case_id")
    advance.add_argument("stage",choices=[s.value for s in Stage])
    advance.add_argument("--actor",required=True)
    advance.add_argument("--approved",action="store_true")
    sub.add_parser("list")
    args=parser.parse_args(argv)
    store=CaseStore(args.db)
    try:
        if args.command=="create":
            case=Case.open(args.service)
            store.save(case)
            print(json.dumps({"id":case.id,"service":case.service,"stage":case.stage.value}))
        elif args.command=="advance":
            case=store.load(args.case_id)
            event=case.move(Stage(args.stage),args.actor,args.approved)
            store.save(case)
            print(json.dumps({"id":case.id,"stage":case.stage.value,"event_hash":event["hash"]}))
        else:
            print(json.dumps([{"id":c.id,"service":c.service,"stage":c.stage.value}
                              for c in store.list_cases()]))
    finally:
        store.close()

if __name__=="__main__":
    main()
