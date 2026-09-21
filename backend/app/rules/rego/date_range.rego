package crpf.evaluation.date_range

default result = "MANUAL_REVIEW"
default explanation = {"reason": "Missing date range parameters"}

range_start := object.get(input.rule, "start_date", null)
range_end := object.get(input.rule, "end_date", null)

missing_range_params if {
    range_start == null
}
missing_range_params if {
    range_end == null
}

# Evaluates whether evidence date falls inside required window
in_range if {
    not missing_range_params
    some ev in input.evidence
    ev.status == "FOUND"
    ev_date := object.get(ev, "date_value", null)
    ev_date != null
    range_start <= ev_date
    ev_date <= range_end
}

result = "MANUAL_REVIEW" if {
    missing_range_params
}

result = "ELIGIBLE" if {
    not missing_range_params
    in_range
}

result = "NOT_ELIGIBLE" if {
    not missing_range_params
    not in_range
}

explanation = {"reason": "Date range evaluation parameters are incomplete"} if {
    missing_range_params
}

explanation = {"reason": sprintf("Evidence date satisfies the required window: %v to %v", [range_start, range_end]), "start_date": range_start, "end_date": range_end} if {
    not missing_range_params
    in_range
}

explanation = {"reason": sprintf("Evidence date falls outside the required window: %v to %v", [range_start, range_end]), "start_date": range_start, "end_date": range_end} if {
    not missing_range_params
    not in_range
}
