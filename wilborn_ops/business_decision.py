"""Hypothetical decision support; never authorizes expenditure or execution."""
from decimal import Decimal
from .feasibility import scenario

def sensitivity(pessimistic, baseline, optimistic):
    results={k:scenario(**v) for k,v in (("pessimistic",pessimistic),("baseline",baseline),("optimistic",optimistic))}
    profits=[Decimal(v["operating_profit_projected"]) for v in results.values()]
    if profits != sorted(profits):
        raise ValueError("scenario profit ordering inconsistent")
    return {"data_class":"hypothetical_scenario","verified_real":False,
            "scenarios":results,"profit_range":str(profits[-1]-profits[0]),
            "downside_loss":str(max(Decimal(0),-profits[0]))}

def rank_opportunities(candidates):
    """Rank assumptions, not verified market demand. Missing evidence blocks ranking."""
    if not isinstance(candidates,list) or len(candidates)>50:
        raise ValueError("bounded candidate list required")
    ranked=[]
    for c in candidates:
        if not isinstance(c["name"],str) or not c["name"].strip():
            raise ValueError("name required")
        evidence=c["evidence_hashes"]
        if not isinstance(evidence,list) or not evidence or any(
            not isinstance(h,str) or len(h)!=64 or any(x not in "0123456789abcdef" for x in h) for h in evidence):
            raise ValueError("evidence references required")
        report=sensitivity(**c["assumptions"])
        ranked.append({"name":c["name"],"evidence_hashes":sorted(set(evidence)),
                       "evidence_verified":False,"financials":report,
                       "execution_authorized":False})
    return sorted(ranked,key=lambda x:(-Decimal(x["financials"]["scenarios"]["pessimistic"]["operating_profit_projected"]),
                                      -Decimal(x["financials"]["scenarios"]["baseline"]["operating_profit_projected"]),x["name"]))

def implementation_plan(candidate):
    return {"data_class":"hypothetical_scenario","opportunity":candidate["name"],
            "execution_authorized":False,"budget_approved":False,
            "monthly_financials":candidate["financials"],
            "milestones":[
                {"stage":"validate demand","acceptance":"independent source and customer demand review","cost":"unestimated"},
                {"stage":"pilot","acceptance":"approved budget and measured unit economics","cost":"unestimated"},
                {"stage":"review","acceptance":"actual pilot results compared with assumptions","cost":"unestimated"}]}
