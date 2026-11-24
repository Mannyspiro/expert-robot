"""Explicit hypothetical business scenarios, never actual financial records."""
from decimal import Decimal, InvalidOperation
def scenario(*, monthly_customers, price, variable_cost, fixed_cost):
    if type(monthly_customers) is not int or not 0 <= monthly_customers <= 1000000:
        raise ValueError("invalid customer assumption")
    def money(value):
        if not isinstance(value,str) or len(value)>32:
            raise ValueError("decimal string required")
        try:
            x=Decimal(value)
        except InvalidOperation as exc:
            raise ValueError("invalid amount") from exc
        if not x.is_finite() or not 0 <= x <= 100000000 or x.as_tuple().exponent < -2:
            raise ValueError("invalid monetary assumption")
        return x
    p,v,f=map(money,(price,variable_cost,fixed_cost))
    margin=p-v
    revenue=p*monthly_customers
    profit=margin*monthly_customers-f
    from decimal import ROUND_CEILING
    return {"data_class":"hypothetical_scenario","currency":"USD","period":"month",
            "customers_assumed":monthly_customers,"revenue_projected":str(revenue),
            "operating_profit_projected":str(profit),
            "break_even_customers":int((f/margin).to_integral_value(rounding=ROUND_CEILING)) if margin>0 else None,
            "verified_real":False}
