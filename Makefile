.PHONY: preflight preflight-targeted railway-preflight sandbox-prepare sandbox-verify compute-policy

preflight:
	bash ./scripts/preflight.sh

preflight-targeted:
	ER_PREFLIGHT_MODE=targeted bash ./scripts/preflight.sh

railway-preflight:
	bash ./scripts/railway-preflight.sh

sandbox-prepare:
	bash ./scripts/railway-sandbox-lane.sh prepare

sandbox-verify:
	bash ./scripts/railway-sandbox-lane.sh verify

compute-policy:
	python3 tests/compute_policy_smoke.py
