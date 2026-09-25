.PHONY: preflight preflight-targeted railway-preflight compute-policy

preflight:
	bash ./scripts/preflight.sh

preflight-targeted:
	ER_PREFLIGHT_MODE=targeted bash ./scripts/preflight.sh

railway-preflight:
	bash ./scripts/railway-preflight.sh

compute-policy:
	python3 tests/compute_policy_smoke.py
