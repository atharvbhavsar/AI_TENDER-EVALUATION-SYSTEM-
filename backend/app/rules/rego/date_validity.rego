package crpf.evaluation.date_validity

default result = "MANUAL_REVIEW"
default explanation = {"reason": "Missing date information for validity assessment"}

# Expects reference_date, and evidence date_value or certificate_data
ref_date := object.get(input.rule, "reference_date", null)
ev := input.evidence[0]
cert_data := object.get(ev, "certificate_data", {})
issue_date := object.get(cert_data, "issue_date", object.get(ev, "date_value", null))
expiry_date := object.get(cert_data, "expiry_date", object.get(ev, "date_value", null))

missing_dates if {
    ref_date == null
}
missing_dates if {
    expiry_date == null
}

# Date comparisons (ISO 8601 YYYY-MM-DD string comparisons are lexically comparable)
is_valid if {
    not missing_dates
    issue_date != null
    issue_date <= ref_date
    ref_date <= expiry_date
}

is_valid if {
    not missing_dates
    issue_date == null
    ref_date <= expiry_date
}

is_expired if {
    not missing_dates
    ref_date > expiry_date
}

result = "MANUAL_REVIEW" if {
    missing_dates
}

result = "ELIGIBLE" if {
    not missing_dates
    is_valid
}

result = "NOT_ELIGIBLE" if {
    not missing_dates
    is_expired
}

explanation = {"reason": "Reference date or certificate expiry date missing from evaluation input"} if {
    missing_dates
}

explanation = {"reason": sprintf("Certificate is valid on reference date: %v <= %v", [ref_date, expiry_date]), "reference_date": ref_date, "expiry_date": expiry_date} if {
    not missing_dates
    is_valid
}

explanation = {"reason": sprintf("Certificate expired prior to reference date: expired on %v, reference date %v", [expiry_date, ref_date]), "reference_date": ref_date, "expiry_date": expiry_date} if {
    not missing_dates
    is_expired
}
