"""Deterministic Python implementation mirroring the Rego policy suite for offline execution & testing."""

import logging
from typing import Any, Dict, List, Optional
from app.db.models.criterion_evaluation import EvaluationResult

logger = logging.getLogger("app.rules.evaluator")


class LocalRegoEvaluator:
    """
    Deterministic rule evaluator executing the exact logic defined in crpf.evaluation Rego policies.
    Guarantees 100% test reproducibility without requiring a running OPA daemon.
    """

    @classmethod
    def evaluate(cls, input_data: Dict[str, Any]) -> Dict[str, Any]:
        rule = input_data.get("rule", {})
        evidence_list: List[Dict[str, Any]] = input_data.get("evidence", [])
        rule_type = rule.get("rule_type", "UNSUPPORTED")
        min_conf = float(rule.get("min_confidence", 0.70))

        # 1. Check for empty evidence
        if not evidence_list:
            return {
                "result": EvaluationResult.MANUAL_REVIEW.value,
                "explanation": {
                    "reason": "No evidence records provided for evaluation",
                    "rule_type": rule_type,
                },
            }

        # 2. Check for evidence status uncertainty
        uncertainty_statuses = {"UNREADABLE", "CONFLICTING", "AMBIGUOUS", "INVALID", "MISSING"}
        for ev in evidence_list:
            status = ev.get("status")
            if status in uncertainty_statuses:
                return {
                    "result": EvaluationResult.MANUAL_REVIEW.value,
                    "explanation": {
                        "reason": f"Evidence record has uncertain status '{status}', routed to manual review",
                        "rule_type": rule_type,
                        "uncertain_evidence_id": ev.get("id"),
                    },
                }

        # 3. Check for low confidence
        for ev in evidence_list:
            conf = float(ev.get("confidence", 1.0))
            if conf < min_conf:
                return {
                    "result": EvaluationResult.MANUAL_REVIEW.value,
                    "explanation": {
                        "reason": f"Evidence confidence {conf:.2f} is below minimum threshold {min_conf:.2f}",
                        "rule_type": rule_type,
                        "confidence": conf,
                        "min_confidence": min_conf,
                    },
                }

        # 4. Route by rule_type
        if rule_type == "NUMERIC_THRESHOLD":
            return cls._eval_numeric_threshold(rule, evidence_list)
        elif rule_type == "EXPERIENCE_COUNT":
            return cls._eval_experience_count(rule, evidence_list)
        elif rule_type == "DATE_VALIDITY":
            return cls._eval_date_validity(rule, evidence_list)
        elif rule_type == "CERTIFICATE_EXISTENCE":
            return cls._eval_certificate_existence(rule, evidence_list)
        elif rule_type == "REGISTRATION_VALIDITY":
            return cls._eval_registration_validity(rule, evidence_list)
        elif rule_type == "BOOLEAN_COMPLIANCE":
            return cls._eval_boolean_compliance(rule, evidence_list)
        elif rule_type == "DATE_RANGE":
            return cls._eval_date_range(rule, evidence_list)
        elif rule_type == "CONDITIONAL_RULE":
            return cls._eval_conditional(rule, evidence_list)
        else:
            return {
                "result": EvaluationResult.MANUAL_REVIEW.value,
                "explanation": {
                    "reason": f"Rule template '{rule_type}' cannot be evaluated deterministically",
                    "rule_type": rule_type,
                },
            }

    @classmethod
    def _eval_numeric_threshold(cls, rule: Dict[str, Any], evidence_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        ev = evidence_list[0]
        actual_val = ev.get("extracted_value")
        if actual_val is None:
            actual_val = ev.get("normalized_value")
        if actual_val is None:
            return {
                "result": EvaluationResult.MANUAL_REVIEW.value,
                "explanation": {"reason": "Evidence lacks numeric value"},
            }

        try:
            actual_num = float(actual_val)
        except (ValueError, TypeError):
            return {
                "result": EvaluationResult.MANUAL_REVIEW.value,
                "explanation": {"reason": f"Unable to parse numeric value '{actual_val}'"},
            }

        req_threshold = float(rule.get("threshold", 0.0))
        op = rule.get("operator", ">=")

        # Check currency / unit mismatch
        req_currency = rule.get("currency")
        ev_currency = ev.get("currency")
        if req_currency and ev_currency and req_currency.upper() != ev_currency.upper():
            return {
                "result": EvaluationResult.MANUAL_REVIEW.value,
                "explanation": {
                    "reason": f"Currency mismatch: required {req_currency}, found {ev_currency}",
                    "required_currency": req_currency,
                    "actual_currency": ev_currency,
                },
            }

        req_unit = rule.get("unit")
        ev_unit = ev.get("unit")
        if req_unit and ev_unit and req_unit.upper() != ev_unit.upper():
            return {
                "result": EvaluationResult.MANUAL_REVIEW.value,
                "explanation": {
                    "reason": f"Unit mismatch without normalization: required {req_unit}, found {ev_unit}",
                    "required_unit": req_unit,
                    "actual_unit": ev_unit,
                },
            }

        # Perform comparison
        satisfied = False
        if op == ">=":
            satisfied = actual_num >= req_threshold
        elif op == ">":
            satisfied = actual_num > req_threshold
        elif op == "<=":
            satisfied = actual_num <= req_threshold
        elif op == "<":
            satisfied = actual_num < req_threshold
        elif op in ("=", "=="):
            satisfied = actual_num == req_threshold
        else:
            return {
                "result": EvaluationResult.MANUAL_REVIEW.value,
                "explanation": {"reason": f"Unsupported operator '{op}'"},
            }

        if satisfied:
            return {
                "result": EvaluationResult.ELIGIBLE.value,
                "explanation": {
                    "reason": f"Requirement satisfied: {actual_num} {op} {req_threshold}",
                    "actual": actual_num,
                    "operator": op,
                    "threshold": req_threshold,
                    "unit": req_unit,
                    "currency": req_currency,
                },
            }
        else:
            return {
                "result": EvaluationResult.NOT_ELIGIBLE.value,
                "explanation": {
                    "reason": f"Requirement not met: {actual_num} is not {op} {req_threshold}",
                    "actual": actual_num,
                    "operator": op,
                    "threshold": req_threshold,
                    "unit": req_unit,
                    "currency": req_currency,
                },
            }

    @classmethod
    def _eval_experience_count(cls, rule: Dict[str, Any], evidence_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        req_count = int(rule.get("threshold") or rule.get("min_count", 1))

        # Check completed_contracts or projects array inside experience_data / extracted_value
        total_projects = 0
        has_count = False
        for ev in evidence_list:
            exp_data = ev.get("experience_data") or {}
            if "completed_contracts" in exp_data and exp_data["completed_contracts"] is not None:
                total_projects += int(exp_data["completed_contracts"])
                has_count = True
            elif isinstance(exp_data.get("projects"), list):
                total_projects += len(exp_data["projects"])
                has_count = True
            elif ev.get("extracted_value") is not None:
                total_projects += int(ev["extracted_value"])
                has_count = True

        if not has_count:
            total_projects = len(evidence_list)

        if total_projects >= req_count:
            return {
                "result": EvaluationResult.ELIGIBLE.value,
                "explanation": {
                    "reason": f"Experience requirement satisfied: {total_projects} >= {req_count} qualifying projects",
                    "actual_count": total_projects,
                    "required_count": req_count,
                },
            }
        else:
            return {
                "result": EvaluationResult.NOT_ELIGIBLE.value,
                "explanation": {
                    "reason": f"Experience requirement not met: {total_projects} projects provided, {req_count} required",
                    "actual_count": total_projects,
                    "required_count": req_count,
                },
            }

    @classmethod
    def _eval_date_validity(cls, rule: Dict[str, Any], evidence_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        ref_date = rule.get("reference_date")
        if not ref_date:
            return {
                "result": EvaluationResult.MANUAL_REVIEW.value,
                "explanation": {"reason": "Reference date missing from evaluation rule"},
            }

        ev = evidence_list[0]
        cert_data = ev.get("certificate_data") or {}
        expiry_date = cert_data.get("expiry_date") or ev.get("date_value")

        if not expiry_date:
            return {
                "result": EvaluationResult.MANUAL_REVIEW.value,
                "explanation": {"reason": "Certificate expiry date missing from evidence"},
            }

        issue_date = cert_data.get("issue_date")
        if issue_date and issue_date > ref_date:
            return {
                "result": EvaluationResult.NOT_ELIGIBLE.value,
                "explanation": {
                    "reason": f"Certificate was issued after reference date: issued on {issue_date}, reference {ref_date}",
                    "issue_date": issue_date,
                    "reference_date": ref_date,
                },
            }

        if ref_date <= expiry_date:
            return {
                "result": EvaluationResult.ELIGIBLE.value,
                "explanation": {
                    "reason": f"Certificate is valid on reference date: {ref_date} <= {expiry_date}",
                    "reference_date": ref_date,
                    "expiry_date": expiry_date,
                },
            }
        else:
            return {
                "result": EvaluationResult.NOT_ELIGIBLE.value,
                "explanation": {
                    "reason": f"Certificate expired prior to reference date: expired on {expiry_date}, reference {ref_date}",
                    "reference_date": ref_date,
                    "expiry_date": expiry_date,
                },
            }

    @classmethod
    def _eval_certificate_existence(cls, rule: Dict[str, Any], evidence_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        req_type = str(rule.get("certificate_name") or rule.get("certificate_type") or "").lower().strip()
        if not req_type:
            return {
                "result": EvaluationResult.MANUAL_REVIEW.value,
                "explanation": {"reason": "Required certificate type not specified in rule"},
            }

        for ev in evidence_list:
            cert_data = ev.get("certificate_data") or {}
            ev_cert_type = str(cert_data.get("certificate_name") or cert_data.get("certificate_type") or "").lower()
            ev_text = str(ev.get("extracted_text", "")).lower()
            if req_type in ev_cert_type or req_type in ev_text:
                return {
                    "result": EvaluationResult.ELIGIBLE.value,
                    "explanation": {
                        "reason": f"Required certificate '{req_type}' confirmed in validated evidence",
                        "certificate_name": req_type,
                    },
                }

        return {
            "result": EvaluationResult.NOT_ELIGIBLE.value,
            "explanation": {
                "reason": f"Required certificate '{req_type}' not found in validated evidence",
                "certificate_name": req_type,
            },
        }

    @classmethod
    def _eval_registration_validity(cls, rule: Dict[str, Any], evidence_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        ref_date = rule.get("reference_date")
        if not ref_date:
            return {
                "result": EvaluationResult.MANUAL_REVIEW.value,
                "explanation": {"reason": "Reference date missing from registration validity rule"},
            }

        ev = evidence_list[0]
        cert_data = ev.get("certificate_data") or {}
        expiry_date = cert_data.get("expiry_date") or ev.get("date_value")

        if not expiry_date:
            return {
                "result": EvaluationResult.MANUAL_REVIEW.value,
                "explanation": {"reason": "Registration expiry date missing from evidence"},
            }

        if ref_date <= expiry_date:
            return {
                "result": EvaluationResult.ELIGIBLE.value,
                "explanation": {
                    "reason": f"Registration is valid on reference date: {ref_date} <= {expiry_date}",
                    "reference_date": ref_date,
                    "expiry_date": expiry_date,
                },
            }
        else:
            return {
                "result": EvaluationResult.NOT_ELIGIBLE.value,
                "explanation": {
                    "reason": f"Registration expired prior to tender date: expired on {expiry_date}, tender date {ref_date}",
                    "reference_date": ref_date,
                    "expiry_date": expiry_date,
                },
            }

    @classmethod
    def _eval_boolean_compliance(cls, rule: Dict[str, Any], evidence_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        req_val = rule.get("required_value", True)
        for ev in evidence_list:
            ext_val = ev.get("extracted_value")
            norm_val = str(ev.get("normalized_value", "")).lower()
            if ext_val is True or ext_val == 1.0 or norm_val in ("true", "yes", "complied", "accepted", "compliant"):
                return {
                    "result": EvaluationResult.ELIGIBLE.value,
                    "explanation": {"reason": "Bidder demonstrated explicit compliance with requirement"},
                }

        return {
            "result": EvaluationResult.NOT_ELIGIBLE.value,
            "explanation": {"reason": "Bidder failed to provide explicit compliance confirmation"},
        }

    @classmethod
    def _eval_date_range(cls, rule: Dict[str, Any], evidence_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        start_date = rule.get("start_date") or rule.get("min_date")
        end_date = rule.get("end_date") or rule.get("max_date")

        if not start_date or not end_date:
            return {
                "result": EvaluationResult.MANUAL_REVIEW.value,
                "explanation": {"reason": "Date range parameters (start_date, end_date) incomplete"},
            }

        for ev in evidence_list:
            ev_date = ev.get("date_value")
            if ev_date and start_date <= ev_date <= end_date:
                return {
                    "result": EvaluationResult.ELIGIBLE.value,
                    "explanation": {
                        "reason": f"Evidence date {ev_date} falls within required window {start_date} to {end_date}",
                        "start_date": start_date,
                        "end_date": end_date,
                        "actual_date": ev_date,
                    },
                }

        return {
            "result": EvaluationResult.NOT_ELIGIBLE.value,
            "explanation": {
                "reason": f"Evidence dates fall outside required window {start_date} to {end_date}",
                "start_date": start_date,
                "end_date": end_date,
            },
        }

    @classmethod
    def _eval_conditional(cls, rule: Dict[str, Any], evidence_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "result": EvaluationResult.MANUAL_REVIEW.value,
            "explanation": {
                "reason": "Conditional rule requires procurement officer discretion and review",
                "condition": rule.get("condition"),
            },
        }
