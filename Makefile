.PHONY: preflight preflight-targeted railway-preflight compute-policy

preflight:
	./scripts/preflight.sh

preflight-targeted:
	ER_PREFLIGHT_MODE=targeted ./scripts/preflight.sh

railway-preflight:
	./scripts/railway-preflight.sh

compute-policy:
	python3 tests/compute_policy_smoke.py
