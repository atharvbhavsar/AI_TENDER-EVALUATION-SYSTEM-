package crpf.evaluation_test

import data.crpf.evaluation

# 1. Numeric threshold tests
test_numeric_threshold_eligible if {
    inp := {
        "rule": {
            "rule_type": "NUMERIC_THRESHOLD",
            "operator": ">=",
            "threshold": 10.0,
            "unit": "CRORE",
            "currency": "INR",
            "min_confidence": 0.70,
        },
        "criterion": {"criterion_code": "FIN-001"},
        "evidence": [{
            "id": "e1",
            "status": "FOUND",
            "extracted_value": 14.5,
            "unit": "CRORE",
            "currency": "INR",
            "confidence": 0.95,
        }],
    }
    evaluation.result with input as inp == "ELIGIBLE"
}

test_numeric_threshold_not_eligible if {
    inp := {
        "rule": {
            "rule_type": "NUMERIC_THRESHOLD",
            "operator": ">=",
            "threshold": 10.0,
            "unit": "CRORE",
            "currency": "INR",
            "min_confidence": 0.70,
        },
        "criterion": {"criterion_code": "FIN-001"},
        "evidence": [{
            "id": "e1",
            "status": "FOUND",
            "extracted_value": 8.5,
            "unit": "CRORE",
            "currency": "INR",
            "confidence": 0.95,
        }],
    }
    evaluation.result with input as inp == "NOT_ELIGIBLE"
}

test_numeric_threshold_currency_mismatch_routes_to_manual_review if {
    inp := {
        "rule": {
            "rule_type": "NUMERIC_THRESHOLD",
            "operator": ">=",
            "threshold": 10.0,
            "unit": "CRORE",
            "currency": "INR",
            "min_confidence": 0.70,
        },
        "criterion": {"criterion_code": "FIN-001"},
        "evidence": [{
            "id": "e1",
            "status": "FOUND",
            "extracted_value": 14.5,
            "unit": "CRORE",
            "currency": "USD",
            "confidence": 0.95,
        }],
    }
    evaluation.result with input as inp == "MANUAL_REVIEW"
}

# 2. Experience count tests
test_experience_count_eligible if {
    inp := {
        "rule": {
            "rule_type": "EXPERIENCE_COUNT",
            "min_count": 3,
            "min_confidence": 0.70,
        },
        "criterion": {"criterion_code": "EXP-001"},
        "evidence": [
            {"id": "e1", "status": "FOUND", "confidence": 0.9},
            {"id": "e2", "status": "FOUND", "confidence": 0.9},
            {"id": "e3", "status": "FOUND", "confidence": 0.9},
        ],
    }
    evaluation.result with input as inp == "ELIGIBLE"
}

test_experience_count_not_eligible if {
    inp := {
        "rule": {
            "rule_type": "EXPERIENCE_COUNT",
            "min_count": 3,
            "min_confidence": 0.70,
        },
        "criterion": {"criterion_code": "EXP-001"},
        "evidence": [
            {"id": "e1", "status": "FOUND", "confidence": 0.9},
            {"id": "e2", "status": "FOUND", "confidence": 0.9},
        ],
    }
    evaluation.result with input as inp == "NOT_ELIGIBLE"
}

# 3. Certificate existence tests
test_certificate_existence_eligible if {
    inp := {
        "rule": {
            "rule_type": "CERTIFICATE_EXISTENCE",
            "certificate_type": "ISO 9001",
            "min_confidence": 0.70,
        },
        "criterion": {"criterion_code": "CERT-001"},
        "evidence": [{
            "id": "e1",
            "status": "FOUND",
            "extracted_text": "Valid ISO 9001:2015 Quality Management Certificate",
            "confidence": 0.92,
        }],
    }
    evaluation.result with input as inp == "ELIGIBLE"
}

# 4. Uncertainty and conflicting evidence safety tests
test_conflicting_evidence_routes_to_manual_review if {
    inp := {
        "rule": {
            "rule_type": "NUMERIC_THRESHOLD",
            "operator": ">=",
            "threshold": 10.0,
            "unit": "CRORE",
            "currency": "INR",
        },
        "criterion": {"criterion_code": "FIN-001"},
        "evidence": [
            {"id": "e1", "status": "FOUND", "extracted_value": 15.0, "unit": "CRORE", "currency": "INR", "confidence": 0.9},
            {"id": "e2", "status": "CONFLICTING", "extracted_value": 8.0, "unit": "CRORE", "currency": "INR", "confidence": 0.9},
        ],
    }
    evaluation.result with input as inp == "MANUAL_REVIEW"
}

test_missing_evidence_routes_to_manual_review if {
    inp := {
        "rule": {
            "rule_type": "CERTIFICATE_EXISTENCE",
            "certificate_type": "ISO 9001",
        },
        "criterion": {"criterion_code": "CERT-001"},
        "evidence": [
            {"id": "e1", "status": "MISSING", "confidence": 1.0},
        ],
    }
    evaluation.result with input as inp == "MANUAL_REVIEW"
}
