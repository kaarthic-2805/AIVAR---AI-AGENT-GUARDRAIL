import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
import json

BASE_DIR = Path(__file__).resolve().parent
POLICY_FILE = BASE_DIR / "action_policies.yaml"


class AuditLogger:
    """In-memory and file-backed audit log for pre-execution action guardrails."""

    def __init__(self):
        self._logs: List[Dict[str, Any]] = []

    def log_event(
        self,
        action: str,
        params: Dict[str, Any],
        outcome: str,
        rule_matched: Optional[Dict[str, Any]] = None,
        agent_id: str = "agent",
        dry_run: bool = False,
        executed: bool = False,
        reason: str = "",
    ) -> Dict[str, Any]:
        entry = {
            "id": f"log_{uuid.uuid4().hex[:8]}",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "agent_id": agent_id,
            "action": action,
            "params": params,
            "outcome": outcome,  # block, require_hitl, log_and_allow
            "rule_id": rule_matched.get("id") if rule_matched else "default",
            "rule_name": rule_matched.get("name") if rule_matched else "Default Policy",
            "rule_description": rule_matched.get("description", "") if rule_matched else "",
            "dry_run": dry_run,
            "executed": executed,
            "reason": reason,
        }
        self._logs.insert(0, entry)
        return entry

    def get_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._logs[:limit]

    def clear(self):
        self._logs.clear()


audit_logger = AuditLogger()


class ActionEvaluator:
    """Pre-execution action evaluator governing agent tool calls against YAML/JSON policy rules."""

    def __init__(self, policy_path: Optional[Path] = None):
        self.policy_path = policy_path or POLICY_FILE
        self.policies = self.load_policies()

    def load_policies(self) -> List[Dict[str, Any]]:
        if not self.policy_path.exists():
            return []
        try:
            with open(self.policy_path, "r", encoding="utf-8") as f:
                if self.policy_path.suffix in [".yaml", ".yml"]:
                    data = yaml.safe_load(f)
                else:
                    data = json.load(f)
                return data.get("policies", [])
        except Exception as exc:
            print(f"Error loading policy file {self.policy_path}: {exc}")
            return []

    def reload(self):
        self.policies = self.load_policies()

    def _eval_condition(self, param_val: Any, operator: str, target_val: Any) -> bool:
        if param_val is None:
            return False

        if operator == ">":
            return float(param_val) > float(target_val)
        elif operator == ">=":
            return float(param_val) >= float(target_val)
        elif operator == "<":
            return float(param_val) < float(target_val)
        elif operator == "<=":
            return float(param_val) <= float(target_val)
        elif operator == "==":
            return str(param_val).lower() == str(target_val).lower()
        elif operator == "!=":
            return str(param_val).lower() != str(target_val).lower()
        elif operator == "contains":
            return str(target_val).lower() in str(param_val).lower()
        elif operator == "not_contains":
            return str(target_val).lower() not in str(param_val).lower()
        elif operator == "ends_with":
            return str(param_val).lower().endswith(str(target_val).lower())
        elif operator == "not_ends_with":
            return not str(param_val).lower().endswith(str(target_val).lower())

        return False

    def evaluate(
        self,
        action: str,
        params: Dict[str, Any],
        agent_id: str = "agent",
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        matched_rule = None

        for rule in self.policies:
            if rule.get("action") == action:
                cond = rule.get("condition", {})
                field_name = cond.get("field")
                op = cond.get("operator")
                target_val = cond.get("value")

                param_val = params.get(field_name)
                if self._eval_condition(param_val, op, target_val):
                    matched_rule = rule
                    break

        if matched_rule:
            outcome = matched_rule.get("outcome", "log_and_allow")
            rule_id = matched_rule.get("id")
            rule_desc = matched_rule.get("description", "")
        else:
            outcome = "log_and_allow"
            rule_id = "default_allow"
            rule_desc = "No matching policy rule; default allow."

        if outcome == "block":
            executed = False
            reason = f"Blocked by rule '{rule_id}': {rule_desc}"
        elif outcome == "require_hitl":
            executed = False
            reason = f"Paused for Human-in-the-Loop approval by rule '{rule_id}': {rule_desc}"
        else:  # log_and_allow
            executed = not dry_run
            reason = f"Allowed by rule '{rule_id}': {rule_desc}"
            if dry_run:
                reason += " (Simulated in Dry Run mode)"

        audit_entry = audit_logger.log_event(
            action=action,
            params=params,
            outcome=outcome,
            rule_matched=matched_rule,
            agent_id=agent_id,
            dry_run=dry_run,
            executed=executed,
            reason=reason,
        )

        return {
            "allowed": outcome != "block",
            "requires_hitl": outcome == "require_hitl",
            "outcome": outcome,
            "rule_id": rule_id,
            "reason": reason,
            "dry_run": dry_run,
            "executed": executed,
            "audit_entry": audit_entry,
        }


# Global evaluator instance
evaluator = ActionEvaluator()
