package crpf.evaluation.experience_count

default result = "NOT_ELIGIBLE"
default explanation = {"reason": "Experience count threshold not satisfied"}

required_count := input.rule.min_count

# Calculate actual qualified count
# May come from single evidence projects list, or count of found experience items
actual_count := count([p |
    some ev in input.evidence
    ev.status == "FOUND"
    projects := object.get(ev, "experience_data", {})
    p_list := object.get(projects, "projects", [])
    some p in p_list
]) if {
    some ev in input.evidence
    projects := object.get(ev, "experience_data", {})
    count(object.get(projects, "projects", [])) > 0
} else := count([ev |
    some ev in input.evidence
    ev.status == "FOUND"
])

satisfied if {
    actual_count >= required_count
}

result = "ELIGIBLE" if {
    satisfied
}

result = "NOT_ELIGIBLE" if {
    not satisfied
}

explanation = {
    "reason": sprintf("Experience requirement satisfied: %v >= %v qualifying projects", [actual_count, required_count]),
    "actual_count": actual_count,
    "required_count": required_count,
} if {
    satisfied
}

explanation = {
    "reason": sprintf("Experience requirement not met: %v projects provided, %v required", [actual_count, required_count]),
    "actual_count": actual_count,
    "required_count": required_count,
} if {
    not satisfied
}
