package crpf.evaluation.numeric_threshold

default result = "NOT_ELIGIBLE"
default explanation = {"reason": "Numeric threshold not satisfied"}

# Extract primary evidence value
target_value := input.evidence[0].extracted_value
threshold := input.rule.threshold
op := input.rule.operator

# Check currency / unit mismatch
currency_mismatch if {
    req_curr := object.get(input.rule, "currency", null)
    ev_curr := object.get(input.evidence[0], "currency", null)
    req_curr != null
    ev_curr != null
    req_curr != ev_curr
}

unit_mismatch if {
    req_unit := object.get(input.rule, "unit", null)
    ev_unit := object.get(input.evidence[0], "unit", null)
    req_unit != null
    ev_unit != null
    req_unit != ev_unit
}

# Currency or unit mismatch routes to MANUAL_REVIEW
result = "MANUAL_REVIEW" if {
    currency_mismatch
}

result = "MANUAL_REVIEW" if {
    unit_mismatch
}

# Operations
satisfied if {
    not currency_mismatch
    not unit_mismatch
    op == ">="
    target_value >= threshold
}

satisfied if {
    not currency_mismatch
    not unit_mismatch
    op == ">"
    target_value > threshold
}

satisfied if {
    not currency_mismatch
    not unit_mismatch
    op == "<="
    target_value <= threshold
}

satisfied if {
    not currency_mismatch
    not unit_mismatch
    op == "<"
    target_value < threshold
}

satisfied if {
    not currency_mismatch
    not unit_mismatch
    op in ["=", "=="]
    target_value == threshold
}

result = "ELIGIBLE" if {
    not currency_mismatch
    not unit_mismatch
    satisfied
}

result = "NOT_ELIGIBLE" if {
    not currency_mismatch
    not unit_mismatch
    not satisfied
}

explanation = {"reason": "Currency mismatch without approved conversion policy", "required_currency": input.rule.currency, "actual_currency": input.evidence[0].currency} if {
    currency_mismatch
}

explanation = {"reason": "Unit mismatch without normalization mapping", "required_unit": input.rule.unit, "actual_unit": input.evidence[0].unit} if {
    not currency_mismatch
    unit_mismatch
}

explanation = {"reason": sprintf("Requirement satisfied: %v %v %v", [target_value, op, threshold]), "actual": target_value, "operator": op, "threshold": threshold} if {
    not currency_mismatch
    not unit_mismatch
    satisfied
}

explanation = {"reason": sprintf("Requirement not met: %v is not %v %v", [target_value, op, threshold]), "actual": target_value, "operator": op, "threshold": threshold} if {
    not currency_mismatch
    not unit_mismatch
    not satisfied
}
