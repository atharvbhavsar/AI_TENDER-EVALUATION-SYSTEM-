package crpf.evaluation.certificate_existence

default result = "NOT_ELIGIBLE"
default explanation = {"reason": "Required certificate not found in validated evidence"}

required_type := lower(object.get(input.rule, "certificate_type", ""))

# Matches certificate type in evidence certificate_data or extracted_text
has_certificate if {
    some ev in input.evidence
    ev.status == "FOUND"
    cert_data := object.get(ev, "certificate_data", {})
    cert_type := lower(object.get(cert_data, "certificate_type", ""))
    contains(cert_type, required_type)
}

has_certificate if {
    some ev in input.evidence
    ev.status == "FOUND"
    text := lower(object.get(ev, "extracted_text", ""))
    contains(text, required_type)
}

result = "ELIGIBLE" if {
    has_certificate
}

result = "NOT_ELIGIBLE" if {
    not has_certificate
}

explanation = {"reason": sprintf("Required certificate '%v' confirmed in validated evidence", [input.rule.certificate_type]), "certificate_type": input.rule.certificate_type} if {
    has_certificate
}

explanation = {"reason": sprintf("Required certificate '%v' not present in validated evidence", [input.rule.certificate_type]), "certificate_type": input.rule.certificate_type} if {
    not has_certificate
}
