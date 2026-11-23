"""Read-only ChatGPT connector tool schema for a future authenticated gateway.

No network endpoint, OAuth or ChatGPT registration is provided by this module.
"""
TOOLS = {
    "list_cases": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
    "get_case_status": {
        "type": "object",
        "properties": {
            "case_id": {"type": "string", "minLength": 1, "maxLength": 64},
        },
        "required": ["case_id"],
        "additionalProperties": False,
    },
    "service_metrics": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

def describe_tools():
    return [
        {"name": name, "description": {
            "list_cases": "List permitted synthetic business cases.",
            "get_case_status": "Get the status of a permitted synthetic case.",
            "service_metrics": "Get synthetic service counts.",
        }[name], "parameters": schema}
        for name, schema in TOOLS.items()
    ]
