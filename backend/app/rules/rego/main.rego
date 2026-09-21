package crpf.evaluation

import data.crpf.evaluation.numeric_threshold
import data.crpf.evaluation.experience_count
import data.crpf.evaluation.date_validity
import data.crpf.evaluation.certificate_existence
import data.crpf.evaluation.registration_validity
import data.crpf.evaluation.boolean_compliance
import data.crpf.evaluation.date_range

# Default decision is always MANUAL_REVIEW for safety
default result = "MANUAL_REVIEW"
default explanation = {"reason": "No evaluation rule matched or input was invalid"}

# Check if evidence contains ambiguity, conflicts, unreadable, invalid, or missing records
has_uncertainty if {
    some ev in input.evidence
    ev.status in ["UNREADABLE", "CONFLICTING", "AMBIGUOUS", "INVALID"]
}

has_uncertainty if {
    count(input.evidence) == 0
}

has_uncertainty if {
    some ev in input.evidence
    ev.status == "MISSING"
}

has_low_confidence if {
    min_conf := object.get(input.rule, "min_confidence", 0.70)
    some ev in input.evidence
    ev.status == "FOUND"
    ev.confidence < min_conf
}

# Route by rule_type when inputs are safe
result = "MANUAL_REVIEW" if {
    has_uncertainty
}

result = "MANUAL_REVIEW" if {
    has_low_confidence
}

result = "MANUAL_REVIEW" if {
    input.rule.rule_type == "UNSUPPORTED"
}

# Delegate to specific rule packages
result = numeric_threshold.result if {
    not has_uncertainty
    not has_low_confidence
    input.rule.rule_type == "NUMERIC_THRESHOLD"
}

result = experience_count.result if {
    not has_uncertainty
    not has_low_confidence
    input.rule.rule_type == "EXPERIENCE_COUNT"
}

result = date_validity.result if {
    not has_uncertainty
    not has_low_confidence
    input.rule.rule_type == "DATE_VALIDITY"
}

result = certificate_existence.result if {
    not has_uncertainty
    not has_low_confidence
    input.rule.rule_type == "CERTIFICATE_EXISTENCE"
}

result = registration_validity.result if {
    not has_uncertainty
    not has_low_confidence
    input.rule.rule_type == "REGISTRATION_VALIDITY"
}

result = boolean_compliance.result if {
    not has_uncertainty
    not has_low_confidence
    input.rule.rule_type == "BOOLEAN_COMPLIANCE"
}

result = date_range.result if {
    not has_uncertainty
    not has_low_confidence
    input.rule.rule_type == "DATE_RANGE"
}

# Aggregate explanation
explanation = {"reason": "Evidence has uncertainty or conflicting status, routed to human review"} if {
    has_uncertainty
}

explanation = {"reason": "Evidence extraction confidence below minimum threshold, routed to human review"} if {
    not has_uncertainty
    has_low_confidence
}

explanation = {"reason": "Criterion cannot be evaluated by supported deterministic rule template"} if {
    input.rule.rule_type == "UNSUPPORTED"
}

explanation = numeric_threshold.explanation if {
    not has_uncertainty
    not has_low_confidence
    input.rule.rule_type == "NUMERIC_THRESHOLD"
}

explanation = experience_count.explanation if {
    not has_uncertainty
    not has_low_confidence
    input.rule.rule_type == "EXPERIENCE_COUNT"
}

explanation = date_validity.explanation if {
    not has_uncertainty
    not has_low_confidence
    input.rule.rule_type == "DATE_VALIDITY"
}

explanation = certificate_existence.explanation if {
    not has_uncertainty
    not has_low_confidence
    input.rule.rule_type == "CERTIFICATE_EXISTENCE"
}

explanation = registration_validity.explanation if {
    not has_uncertainty
    not has_low_confidence
    input.rule.rule_type == "REGISTRATION_VALIDITY"
}

explanation = boolean_compliance.explanation if {
    not has_uncertainty
    not has_low_confidence
    input.rule.rule_type == "BOOLEAN_COMPLIANCE"
}

explanation = date_range.explanation if {
    not has_uncertainty
    not has_low_confidence
    input.rule.rule_type == "DATE_RANGE"
}
