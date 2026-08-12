"""
Simulation Harness for Agent Action Guardrails
Evaluates agent tool execution scenarios against policy rulesets (YAML/JSON).
Triggers block, require_hitl, log_and_allow, and dry-run evaluation modes.
"""

from typing import Any, Dict, List
from action_guardrail import evaluator, audit_logger


def run_simulation(dry_run: bool = False) -> Dict[str, Any]:
    """Run all target test scenarios through the Action Evaluator."""
    test_scenarios = [
        {
            "id": "scenario_1_bulk_delete",
            "name": "Bulk Database Delete (500 records)",
            "action": "delete_records",
            "params": {"table": "property_listings", "record_count": 500},
            "expected_outcome": "block",
        },
        {
            "id": "scenario_2_small_delete",
            "name": "Small Database Delete (5 records)",
            "action": "delete_records",
            "params": {"table": "draft_listings", "record_count": 5},
            "expected_outcome": "log_and_allow",
        },
        {
            "id": "scenario_3_external_email",
            "name": "Send Email to External Domain (client@gmail.com)",
            "action": "send_email",
            "params": {
                "recipient": "client@gmail.com",
                "subject": "Real Estate Proposal",
                "body": "Here is the property proposal.",
            },
            "expected_outcome": "require_hitl",
        },
        {
            "id": "scenario_4_internal_email",
            "name": "Send Email to Internal Domain (agent@realestate.com)",
            "action": "send_email",
            "params": {
                "recipient": "agent@realestate.com",
                "subject": "Internal Listing Audit",
                "body": "Weekly report attached.",
            },
            "expected_outcome": "log_and_allow",
        },
        {
            "id": "scenario_5_confidential_read",
            "name": "Read File Path containing 'confidential'",
            "action": "read_path",
            "params": {"path": "/documents/confidential_title_deed.pdf"},
            "expected_outcome": "log_and_allow",
        },
        {
            "id": "scenario_6_standard_read",
            "name": "Read Standard File Path",
            "action": "read_path",
            "params": {"path": "/public/brochure.pdf"},
            "expected_outcome": "log_and_allow",
        },
    ]

    evaluator.reload()
    results: List[Dict[str, Any]] = []
    passed_count = 0

    print("=" * 65)
    print(f"RUNNING ACTION GUARDRAIL SIMULATION HARNESS (Dry Run: {dry_run})")
    print("=" * 65)

    for sc in test_scenarios:
        res = evaluator.evaluate(
            action=sc["action"],
            params=sc["params"],
            agent_id="simulation_agent",
            dry_run=dry_run,
        )

        outcome_matched = res["outcome"] == sc["expected_outcome"]
        if outcome_matched:
            passed_count += 1

        scenario_res = {
            "scenario_id": sc["id"],
            "scenario_name": sc["name"],
            "action": sc["action"],
            "params": sc["params"],
            "expected_outcome": sc["expected_outcome"],
            "actual_outcome": res["outcome"],
            "rule_id": res["rule_id"],
            "passed": outcome_matched,
            "reason": res["reason"],
            "audit_entry": res["audit_entry"],
        }
        results.append(scenario_res)

        status_symbol = "[PASS]" if outcome_matched else "[FAIL]"
        print(f"{status_symbol} {sc['name']}")
        print(f"    Expected: {sc['expected_outcome']} | Actual: {res['outcome']}")
        print(f"    Matched Rule: {res['rule_id']}")
        print(f"    Reason: {res['reason']}\n")

    summary = {
        "total": len(test_scenarios),
        "passed": passed_count,
        "failed": len(test_scenarios) - passed_count,
        "dry_run": dry_run,
        "scenarios": results,
        "audit_logs": audit_logger.get_logs(limit=len(test_scenarios)),
    }

    print("=" * 65)
    print(f"SIMULATION SUMMARY: {passed_count}/{len(test_scenarios)} Scenarios Passed")
    print("=" * 65)

    return summary


if __name__ == "__main__":
    run_simulation(dry_run=False)
