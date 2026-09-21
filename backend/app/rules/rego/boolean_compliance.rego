package crpf.evaluation.boolean_compliance

default result = "NOT_ELIGIBLE"
default explanation = {"reason": "Boolean compliance requirement not satisfied"}

required_bool := object.get(input.rule, "required_value", true)

# Extract boolean from structured evidence (extracted_value or normalized_value or status)
is_compliant if {
    some ev in input.evidence
    ev.status == "FOUND"
    ev.extracted_value == 1.0
    required_bool == true
}

is_compliant if {
    some ev in input.evidence
    ev.status == "FOUND"
    lower(object.get(ev, "normalized_value", "")) in ["true", "yes", "complied", "accepted"]
    required_bool == true
}

result = "ELIGIBLE" if {
    is_compliant
}

result = "NOT_ELIGIBLE" if {
    not is_compliant
}

explanation = {"reason": "Bidder demonstrated explicit compliance with requirement"} if {
    is_compliant
}

explanation = {"reason": "Bidder failed to provide explicit compliance confirmation"} if {
    not is_compliant
}
