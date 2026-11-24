"""Compose existing research stages without granting network or business access."""
from .research_retrieval import accept_receipt
from .research_html import extract_html
from .research_tabular import analyze_numeric_csv
from .research_analysis import analyze_evidence

def research_report(receipt, *, numeric_column=None):
    accepted = accept_receipt(receipt)
    evidence = accepted["evidence"]
    report = analyze_evidence([evidence])
    report["source_url"] = evidence.url
    report["retrieval_assurance"] = accepted["retrieval_assurance"]
    report["untrusted_content"] = True
    if receipt.content_type == "text/html":
        if numeric_column is not None:
            raise ValueError("numeric analysis requires CSV")
        report["extracted_text"] = extract_html(evidence).text
    elif receipt.content_type == "text/csv" and numeric_column is not None:
        report["numeric_analysis"] = analyze_numeric_csv(evidence, numeric_column)
    elif numeric_column is not None:
        raise ValueError("numeric analysis requires CSV")
    return report
