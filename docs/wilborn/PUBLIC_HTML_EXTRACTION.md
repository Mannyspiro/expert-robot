# Merlin offline public HTML extraction

Added a bounded HTML-to-text stage for already-ingested public research evidence. It drops script/style/template/noscript/svg contents, caps extracted text, preserves URL and source SHA-256, and labels all extracted page text as untrusted.

**Not a web scraper:** no HTTP requests, DNS, redirects, browser execution, robots checks or site crawling occur. HTML extraction does not neutralize prompt injection; the untrusted flag must remain enforced by the actual Merlin model/tool boundary. No real client records are used.

Next: integrate a network-isolated approved retrieval provider with DNS/IP egress enforcement, redirect revalidation, rate limits, legal access controls and reproducible source citations. Then test a complete retrieval -> extraction -> typed analysis -> citation report against a real public source. Keep synthetic demo, public research and production business data isolated.
