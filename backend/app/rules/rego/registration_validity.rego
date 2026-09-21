package crpf.evaluation.registration_validity

default result = "MANUAL_REVIEW"
default explanation = {"reason": "Missing registration details for validity evaluation"}

ref_date := object.get(input.rule, "reference_date", null)
ev := input.evidence[0]
reg_data := object.get(ev, "certificate_data", {})
reg_start := object.get(reg_data, "issue_date", object.get(ev, "date_value", null))
reg_expiry := object.get(reg_data, "expiry_date", object.get(ev, "date_value", null))

missing_reg_dates if {
    ref_date == null
}
missing_reg_dates if {
    reg_expiry == null
}

is_reg_valid if {
    not missing_reg_dates
    reg_start != null
    reg_start <= ref_date
    ref_date <= reg_expiry
}

is_reg_valid if {
    not missing_reg_dates
    reg_start == null
    ref_date <= reg_expiry
}

is_reg_expired if {
    not missing_reg_dates
    ref_date > reg_expiry
}

result = "MANUAL_REVIEW" if {
    missing_reg_dates
}

result = "ELIGIBLE" if {
    not missing_reg_dates
    is_reg_valid
}

result = "NOT_ELIGIBLE" if {
    not missing_reg_dates
    is_reg_expired
}

explanation = {"reason": "Reference date or registration expiry date missing"} if {
    missing_reg_dates
}

explanation = {"reason": sprintf("Registration is valid on reference date: %v <= %v", [ref_date, reg_expiry]), "reference_date": ref_date, "expiry_date": reg_expiry} if {
    not missing_reg_dates
    is_reg_valid
}

explanation = {"reason": sprintf("Registration expired prior to tender date: expired on %v, tender date %v", [reg_expiry, ref_date]), "reference_date": ref_date, "expiry_date": reg_expiry} if {
    not missing_reg_dates
    is_reg_expired
}
