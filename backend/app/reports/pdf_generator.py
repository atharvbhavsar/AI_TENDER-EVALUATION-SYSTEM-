"""PDF Report Generator for CRPF Tender Procurement Evaluation using ReportLab."""

import io
from typing import Any, Dict, List, Optional
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from app.reports.schemas import BidderExplanationResponse


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas for dynamic 'Page X of Y' pagination and official header/footer."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._saved_page_states: List[Any] = []

    def showPage(self) -> None:
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count: int) -> None:
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#4A5568"))

        # Top Header
        self.drawString(54, 750, "CRPF PROCUREMENT EVALUATION PLATFORM - OFFICIAL AUDIT ARTIFACT")
        self.drawRightString(558, 750, "CONFIDENTIAL / GOVERNMENT USE ONLY")
        self.setStrokeColor(colors.HexColor("#CBD5E0"))
        self.setLineWidth(0.5)
        self.line(54, 744, 558, 744)

        # Bottom Footer
        self.line(54, 45, 558, 45)
        self.drawString(54, 32, "CRPF Technical & Eligibility Analysis System | Derived Evaluation Artifact")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 32, page_str)
        self.restoreState()


class PDFReportGenerator:
    """Renders structured, formal procurement evaluation reports into high-fidelity PDF binaries."""

    @staticmethod
    def _build_styles() -> Dict[str, ParagraphStyle]:
        styles = getSampleStyleSheet()
        custom = {
            "DocTitle": ParagraphStyle(
                "DocTitle",
                parent=styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=15,
                leading=19,
                alignment=TA_CENTER,
                textColor=colors.HexColor("#1A202C"),
            ),
            "DocSubtitle": ParagraphStyle(
                "DocSubtitle",
                parent=styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=10,
                leading=14,
                alignment=TA_CENTER,
                textColor=colors.HexColor("#2B6CB0"),
            ),
            "SectionHeader": ParagraphStyle(
                "SectionHeader",
                parent=styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=11,
                leading=15,
                textColor=colors.HexColor("#1A365D"),
                spaceBefore=10,
                spaceAfter=4,
            ),
            "SubHeader": ParagraphStyle(
                "SubHeader",
                parent=styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=8.5,
                leading=11,
                textColor=colors.HexColor("#2D3748"),
            ),
            "Body": ParagraphStyle(
                "Body",
                parent=styles["Normal"],
                fontName="Helvetica",
                fontSize=8,
                leading=11,
                textColor=colors.HexColor("#2D3748"),
            ),
            "BodyBold": ParagraphStyle(
                "BodyBold",
                parent=styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=8,
                leading=11,
                textColor=colors.HexColor("#1A202C"),
            ),
            "TableCell": ParagraphStyle(
                "TableCell",
                parent=styles["Normal"],
                fontName="Helvetica",
                fontSize=7.5,
                leading=9.5,
                textColor=colors.HexColor("#2D3748"),
            ),
            "TableCellCode": ParagraphStyle(
                "TableCellCode",
                parent=styles["Normal"],
                fontName="Courier",
                fontSize=7,
                leading=8.5,
                textColor=colors.HexColor("#2D3748"),
            ),
            "TableHead": ParagraphStyle(
                "TableHead",
                parent=styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=8,
                leading=10,
                textColor=colors.white,
                alignment=TA_CENTER,
            ),
            "VerdictEligible": ParagraphStyle(
                "VerdictEligible",
                parent=styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=8,
                leading=10,
                textColor=colors.HexColor("#22543D"),
            ),
            "VerdictNotEligible": ParagraphStyle(
                "VerdictNotEligible",
                parent=styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=8,
                leading=10,
                textColor=colors.HexColor("#742A2A"),
            ),
            "VerdictManualReview": ParagraphStyle(
                "VerdictManualReview",
                parent=styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=8,
                leading=10,
                textColor=colors.HexColor("#7B341E"),
            ),
            "NoticeBox": ParagraphStyle(
                "NoticeBox",
                parent=styles["Normal"],
                fontName="Helvetica-Oblique",
                fontSize=7.5,
                leading=10,
                textColor=colors.HexColor("#4A5568"),
            ),
        }
        return custom

    @classmethod
    def generate_bidder_report(
        cls,
        explanation: BidderExplanationResponse,
        audit_summary: Optional[List[Dict[str, Any]]] = None,
        include_source_snippets: bool = True,
        report_meta: Optional[Dict[str, Any]] = None,
    ) -> bytes:
        """Generate a complete, formal PDF Bidder Evaluation Report with Sections A through G."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=54,
            rightMargin=54,
            topMargin=60,
            bottomMargin=60,
        )

        styles = cls._build_styles()
        elements = []
        meta = report_meta or {}

        # Document Header
        elements.append(Paragraph("CENTRAL RESERVE POLICE FORCE (CRPF)", styles["DocTitle"]))
        elements.append(Paragraph("BIDDER ELIGIBILITY EVALUATION & DECISION AUDIT REPORT", styles["DocSubtitle"]))
        elements.append(Spacer(1, 6))
        elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#2B6CB0"), spaceBefore=2, spaceAfter=8))

        # =========================================================================
        # SECTION A - REPORT INFORMATION
        # =========================================================================
        elements.append(Paragraph("SECTION A - REPORT INFORMATION", styles["SectionHeader"]))
        meta_data = [
            [
                Paragraph("<b>Report ID:</b>", styles["Body"]),
                Paragraph(str(meta.get("report_id", "N/A")), styles["TableCellCode"]),
                Paragraph("<b>Generation Date:</b>", styles["Body"]),
                Paragraph(str(meta.get("generated_at", "N/A")), styles["Body"]),
            ],
            [
                Paragraph("<b>Tender Number:</b>", styles["Body"]),
                Paragraph(explanation.tender_number, styles["BodyBold"]),
                Paragraph("<b>Tender Version:</b>", styles["Body"]),
                Paragraph(f"v{explanation.tender_version_number}", styles["BodyBold"]),
            ],
            [
                Paragraph("<b>Tender Title:</b>", styles["Body"]),
                Paragraph(explanation.tender_title, styles["BodyBold"]),
                Paragraph("<b>Report Version:</b>", styles["Body"]),
                Paragraph(f"v{meta.get('report_version', 1)}", styles["BodyBold"]),
            ],
            [
                Paragraph("<b>Bidder Name:</b>", styles["Body"]),
                Paragraph(explanation.bidder_name, styles["BodyBold"]),
                Paragraph("<b>Bidder ID:</b>", styles["Body"]),
                Paragraph(str(explanation.bidder_id)[:18] + "...", styles["TableCellCode"]),
            ],
            [
                Paragraph("<b>Submission ID:</b>", styles["Body"]),
                Paragraph(str(explanation.bid_submission_id), styles["TableCellCode"]),
                Paragraph("<b>Evaluation Run ID:</b>", styles["Body"]),
                Paragraph(str(explanation.evaluation_run_id or "N/A")[:18] + "...", styles["TableCellCode"]),
            ],
        ]
        meta_table = Table(meta_data, colWidths=[100, 152, 100, 152])
        meta_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EDF2F7")),
                ("PADDING", (0, 0), (-1, -1), 3.5),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E2E8F0")),
            ])
        )
        elements.append(meta_table)
        elements.append(Spacer(1, 8))

        # =========================================================================
        # SECTION B - EXECUTIVE SUMMARY
        # =========================================================================
        elements.append(Paragraph("SECTION B - EXECUTIVE SUMMARY & VERDICT COMPARISON", styles["SectionHeader"]))
        auto_style = (
            styles["VerdictEligible"] if explanation.automated_overall_result.value == "ELIGIBLE"
            else (styles["VerdictNotEligible"] if explanation.automated_overall_result.value == "NOT_ELIGIBLE" else styles["VerdictManualReview"])
        )
        final_style = (
            styles["VerdictEligible"] if explanation.final_decision_state.value == "ELIGIBLE"
            else (styles["VerdictNotEligible"] if explanation.final_decision_state.value == "NOT_ELIGIBLE" else styles["VerdictManualReview"])
        )

        exec_data = [
            [
                Paragraph("<b>Automated OPA Result</b>", styles["TableHead"]),
                Paragraph("<b>Human Officer Decision</b>", styles["TableHead"]),
                Paragraph("<b>Final Decision State</b>", styles["TableHead"]),
                Paragraph("<b>Total Criteria</b>", styles["TableHead"]),
                Paragraph("<b>Mandatory Pass / Total</b>", styles["TableHead"]),
            ],
            [
                Paragraph(explanation.automated_overall_result.value, auto_style),
                Paragraph(explanation.human_overall_decision.value if explanation.human_overall_decision else "NO OVERRIDE", styles["TableCell"]),
                Paragraph(explanation.final_decision_state.value, final_style),
                Paragraph(str(explanation.total_criteria), styles["TableCell"]),
                Paragraph(f"{explanation.mandatory_eligible_count} / {explanation.mandatory_criteria_count}", styles["TableCell"]),
            ],
        ]
        exec_table = Table(exec_data, colWidths=[105, 105, 105, 95, 94])
        exec_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2B6CB0")),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("PADDING", (0, 0), (-1, -1), 4.5),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
            ])
        )
        elements.append(exec_table)
        elements.append(Spacer(1, 4))

        # Evidence Issue Breakdown Sub-grid
        ev_issue_text = (
            f"<b>Evidence Integrity Metrics:</b> "
            f"Missing: <b>{explanation.missing_evidence_count}</b> | "
            f"Conflicting: <b>{explanation.conflicting_evidence_count}</b> | "
            f"Unreadable: <b>{explanation.unreadable_evidence_count}</b> | "
            f"Ambiguous: <b>{explanation.ambiguous_evidence_count}</b> | "
            f"Invalid: <b>{explanation.invalid_evidence_count}</b>"
        )
        elements.append(Paragraph(ev_issue_text, styles["NoticeBox"]))
        elements.append(Spacer(1, 8))

        # =========================================================================
        # SECTION C - CRITERION EVALUATION
        # =========================================================================
        elements.append(Paragraph("SECTION C - CRITERION-LEVEL DETAILED EVALUATIONS", styles["SectionHeader"]))
        crit_rows = [
            [
                Paragraph("<b>#</b>", styles["TableHead"]),
                Paragraph("<b>Criterion & Clause</b>", styles["TableHead"]),
                Paragraph("<b>Type</b>", styles["TableHead"]),
                Paragraph("<b>Extracted / Normalized</b>", styles["TableHead"]),
                Paragraph("<b>Source Document & Location</b>", styles["TableHead"]),
                Paragraph("<b>Rule & Ver.</b>", styles["TableHead"]),
                Paragraph("<b>Automated / Officer</b>", styles["TableHead"]),
            ]
        ]

        for idx, ce in enumerate(explanation.criteria_explanations, start=1):
            crit_res_style = (
                styles["VerdictEligible"] if ce.automated_result.value == "ELIGIBLE"
                else (styles["VerdictNotEligible"] if ce.automated_result.value == "NOT_ELIGIBLE" else styles["VerdictManualReview"])
            )
            doc_str = f"{ce.primary_document_name or 'N/A'}"
            if ce.primary_page_number:
                doc_str += f"<br/>p. {ce.primary_page_number}"
            if ce.primary_bbox:
                doc_str += f" | bbox"

            decision_str = "-"
            if ce.human_decision:
                decision_str = f"{ce.human_decision.value}"
                if ce.is_overridden and ce.override_reason:
                    decision_str += f"<br/><i>Override: {ce.override_reason[:30]}...</i>"

            val_str = f"Ext: {ce.extracted_value or 'N/A'}"
            if ce.normalized_value is not None:
                val_str += f"<br/>Norm: {ce.normalized_value}"
            if ce.evidence_status and ce.evidence_status != "FOUND":
                val_str += f"<br/><i>({ce.evidence_status})</i>"

            rule_str = f"{ce.rule_type or 'DEFAULT'}"
            if ce.rule_version:
                rule_str += f"<br/>({ce.rule_version})"

            clause_str = f"<b>{ce.requirement_name}</b>"
            if ce.source_clause:
                clause_str += f"<br/><font color='#718096'>{ce.source_clause[:50]}...</font>"

            crit_rows.append([
                Paragraph(str(idx), styles["TableCell"]),
                Paragraph(clause_str, styles["TableCell"]),
                Paragraph(f"{ce.category}<br/><b>{ce.requirement_type}</b>", styles["TableCell"]),
                Paragraph(val_str, styles["TableCell"]),
                Paragraph(doc_str, styles["TableCell"]),
                Paragraph(rule_str, styles["TableCell"]),
                Paragraph(f"{ce.automated_result.value}<br/><b>{decision_str}</b>", crit_res_style),
            ])

        crit_table = Table(crit_rows, colWidths=[20, 110, 50, 104, 100, 60, 60])
        crit_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2D3748")),
                ("PADDING", (0, 0), (-1, -1), 3.5),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E2E8F0")),
            ])
        )
        elements.append(crit_table)
        elements.append(Spacer(1, 8))

        # =========================================================================
        # SECTION D - EVIDENCE SUMMARY & PROVENANCE
        # =========================================================================
        elements.append(Paragraph("SECTION D - EVIDENCE SUMMARY & PROVENANCE", styles["SectionHeader"]))
        all_ev_items: List[Dict[str, Any]] = []
        for ce in explanation.criteria_explanations:
            for ev in ce.evidence_items:
                all_ev_items.append({
                    "criterion_name": ce.requirement_name,
                    "item": ev,
                })

        if all_ev_items:
            ev_rows = [
                [
                    Paragraph("<b>#</b>", styles["TableHead"]),
                    Paragraph("<b>Criterion</b>", styles["TableHead"]),
                    Paragraph("<b>Document & Hash</b>", styles["TableHead"]),
                    Paragraph("<b>Pg</b>", styles["TableHead"]),
                    Paragraph("<b>Extracted Value</b>", styles["TableHead"]),
                    Paragraph("<b>Normalized Value</b>", styles["TableHead"]),
                    Paragraph("<b>Status</b>", styles["TableHead"]),
                    Paragraph("<b>Conf</b>", styles["TableHead"]),
                ]
            ]
            for idx, entry in enumerate(all_ev_items, start=1):
                ev = entry["item"]
                doc_name_str = f"{ev.document_name or 'N/A'}"
                if ev.document_hash:
                    doc_name_str += f"<br/><font color='#718096'>{ev.document_hash[:12]}...</font>"

                conf_str = f"{ev.confidence_score:.2f}" if ev.confidence_score is not None else "1.00"

                ev_rows.append([
                    Paragraph(str(idx), styles["TableCell"]),
                    Paragraph(entry["criterion_name"][:35], styles["TableCell"]),
                    Paragraph(doc_name_str, styles["TableCell"]),
                    Paragraph(str(ev.page_number or "-"), styles["TableCell"]),
                    Paragraph(str(ev.extracted_value or "-")[:40], styles["TableCell"]),
                    Paragraph(str(ev.normalized_value or "-")[:40], styles["TableCell"]),
                    Paragraph(str(ev.evidence_status), styles["TableCell"]),
                    Paragraph(conf_str, styles["TableCell"]),
                ])

            ev_table = Table(ev_rows, colWidths=[20, 100, 104, 30, 80, 80, 50, 40])
            ev_table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4A5568")),
                    ("PADDING", (0, 0), (-1, -1), 3),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E2E8F0")),
                ])
            )
            elements.append(ev_table)
        else:
            elements.append(Paragraph("No discrete evidence items found.", styles["Body"]))
        elements.append(Spacer(1, 8))

        # =========================================================================
        # SECTION E - MANUAL REVIEW CASES & OFFICER DECISIONS
        # =========================================================================
        elements.append(Paragraph("SECTION E - HUMAN MANUAL REVIEW & OFFICER DECISIONS", styles["SectionHeader"]))
        if explanation.review_cases_summary:
            rc_rows = [
                [
                    Paragraph("<b>Case Title</b>", styles["TableHead"]),
                    Paragraph("<b>Issue Type</b>", styles["TableHead"]),
                    Paragraph("<b>Status</b>", styles["TableHead"]),
                    Paragraph("<b>Priority</b>", styles["TableHead"]),
                    Paragraph("<b>Recorded Decision</b>", styles["TableHead"]),
                    Paragraph("<b>Decisions Count</b>", styles["TableHead"]),
                ]
            ]
            for rc in explanation.review_cases_summary:
                rc_rows.append([
                    Paragraph(rc["title"], styles["TableCell"]),
                    Paragraph(rc["issue_type"], styles["TableCell"]),
                    Paragraph(rc["status"], styles["TableCell"]),
                    Paragraph(rc["priority"], styles["TableCell"]),
                    Paragraph(rc["latest_decision"] or "Pending", styles["TableCell"]),
                    Paragraph(str(rc.get("decision_count", 0)), styles["TableCell"]),
                ])
            rc_table = Table(rc_rows, colWidths=[110, 80, 64, 60, 110, 80])
            rc_table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7B341E")),
                    ("PADDING", (0, 0), (-1, -1), 3.5),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E2E8F0")),
                ])
            )
            elements.append(rc_table)
        else:
            elements.append(Paragraph("No human review cases flagged for this submission.", styles["Body"]))
        elements.append(Spacer(1, 8))

        # =========================================================================
        # SECTION F - EVALUATION LINEAGE & TRACEABILITY
        # =========================================================================
        elements.append(Paragraph("SECTION F - EVALUATION LINEAGE & TRACEABILITY", styles["SectionHeader"]))
        lineage_text = (
            f"<b>Traceability Chain:</b><br/>"
            f"Tender (<b>{explanation.tender_number}</b>) "
            f"-> Version (<b>v{explanation.tender_version_number}</b>) "
            f"-> Criteria (<b>{explanation.total_criteria} Approved</b>)<br/>"
            f"-> Bidder (<b>{explanation.bidder_name}</b>) "
            f"-> Submission (<b>{str(explanation.bid_submission_id)[:8]}...</b>) "
            f"-> Evidence Validation "
            f"-> OPA Rule Engine<br/>"
            f"-> Automated Verdict (<b>{explanation.automated_overall_result.value}</b>) "
            f"-> Human Review (<b>{explanation.human_overall_decision.value if explanation.human_overall_decision else 'None'}</b>) "
            f"-> Final State (<b>{explanation.final_decision_state.value}</b>)"
        )
        lineage_p = Paragraph(lineage_text, styles["NoticeBox"])
        elements.append(lineage_p)
        elements.append(Spacer(1, 8))

        # =========================================================================
        # SECTION G - AUDIT SUMMARY
        # =========================================================================
        if audit_summary:
            elements.append(Paragraph("SECTION G - SYSTEM AUDIT & PROVENANCE SUMMARY", styles["SectionHeader"]))
            audit_rows = [
                [
                    Paragraph("<b>Timestamp</b>", styles["TableHead"]),
                    Paragraph("<b>Action</b>", styles["TableHead"]),
                    Paragraph("<b>Entity</b>", styles["TableHead"]),
                    Paragraph("<b>Actor</b>", styles["TableHead"]),
                    Paragraph("<b>Details / Reason</b>", styles["TableHead"]),
                ]
            ]
            for al in audit_summary[:15]:
                ts = al.get("timestamp", "")
                if isinstance(ts, str) and len(ts) > 19:
                    ts = ts[:19]
                audit_rows.append([
                    Paragraph(str(ts), styles["TableCell"]),
                    Paragraph(al.get("action", ""), styles["TableCell"]),
                    Paragraph(f"{al.get('entity_type', '')}:{al.get('entity_id', '')[:8]}", styles["TableCell"]),
                    Paragraph(str(al.get("actor_id", "SYSTEM"))[:12], styles["TableCell"]),
                    Paragraph(al.get("reason") or "-", styles["TableCell"]),
                ])
            audit_table = Table(audit_rows, colWidths=[85, 105, 84, 80, 150])
            audit_table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4A5568")),
                    ("PADDING", (0, 0), (-1, -1), 3),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E2E8F0")),
                ])
            )
            elements.append(audit_table)

        # Build PDF
        doc.build(elements, canvasmaker=NumberedCanvas)
        buffer.seek(0)
        return buffer.getvalue()

    @classmethod
    def generate_consolidated_report(
        cls,
        tender_meta: Dict[str, Any],
        bidders_explanations: List[BidderExplanationResponse],
        audit_summary: Optional[List[Dict[str, Any]]] = None,
        report_meta: Optional[Dict[str, Any]] = None,
    ) -> bytes:
        """Generate a complete Consolidated Tender Evaluation Report (No ranking, scoring, or winner selection)."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=54,
            rightMargin=54,
            topMargin=60,
            bottomMargin=60,
        )

        styles = cls._build_styles()
        elements = []
        meta = report_meta or {}

        # Document Header
        elements.append(Paragraph("CENTRAL RESERVE POLICE FORCE (CRPF)", styles["DocTitle"]))
        elements.append(Paragraph("CONSOLIDATED TENDER EVALUATION & BIDDER COMPARISON REPORT", styles["DocSubtitle"]))
        elements.append(Spacer(1, 6))
        elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#2B6CB0"), spaceBefore=2, spaceAfter=8))

        # SECTION A: TENDER SPECIFICATIONS & REPORT INFORMATION
        elements.append(Paragraph("SECTION A - TENDER SPECIFICATIONS & REPORT INFORMATION", styles["SectionHeader"]))
        meta_data = [
            [
                Paragraph("<b>Report ID:</b>", styles["Body"]),
                Paragraph(str(meta.get("report_id", "N/A")), styles["TableCellCode"]),
                Paragraph("<b>Generation Date:</b>", styles["Body"]),
                Paragraph(str(meta.get("generated_at", "N/A")), styles["Body"]),
            ],
            [
                Paragraph("<b>Tender Number:</b>", styles["Body"]),
                Paragraph(tender_meta.get("tender_number", "N/A"), styles["BodyBold"]),
                Paragraph("<b>Tender Version:</b>", styles["Body"]),
                Paragraph(f"v{tender_meta.get('version_number', 1)}", styles["BodyBold"]),
            ],
            [
                Paragraph("<b>Tender Title:</b>", styles["Body"]),
                Paragraph(tender_meta.get("title", "N/A"), styles["BodyBold"]),
                Paragraph("<b>Total Submissions:</b>", styles["Body"]),
                Paragraph(str(len(bidders_explanations)), styles["BodyBold"]),
            ],
        ]
        meta_table = Table(meta_data, colWidths=[100, 152, 100, 152])
        meta_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EDF2F7")),
                ("PADDING", (0, 0), (-1, -1), 3.5),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E2E8F0")),
            ])
        )
        elements.append(meta_table)
        elements.append(Spacer(1, 8))

        # SECTION B: COMPARATIVE BIDDER ELIGIBILITY MATRIX
        elements.append(Paragraph("SECTION B - COMPARATIVE BIDDER ELIGIBILITY MATRIX", styles["SectionHeader"]))
        elements.append(
            Paragraph(
                "<i>Note: This matrix represents authoritative automated evaluations and human officer determinations. "
                "Per CRPF procurement governance, no ranking, scoring, or winner selection is performed.</i>",
                styles["NoticeBox"],
            )
        )
        elements.append(Spacer(1, 4))

        matrix_rows = [
            [
                Paragraph("<b>#</b>", styles["TableHead"]),
                Paragraph("<b>Bidder Name</b>", styles["TableHead"]),
                Paragraph("<b>Automated OPA</b>", styles["TableHead"]),
                Paragraph("<b>Officer Decision</b>", styles["TableHead"]),
                Paragraph("<b>Final State</b>", styles["TableHead"]),
                Paragraph("<b>Mandatory Pass</b>", styles["TableHead"]),
                Paragraph("<b>Review / Issues</b>", styles["TableHead"]),
            ]
        ]

        for idx, be in enumerate(bidders_explanations, start=1):
            auto_s = (
                styles["VerdictEligible"] if be.automated_overall_result.value == "ELIGIBLE"
                else (styles["VerdictNotEligible"] if be.automated_overall_result.value == "NOT_ELIGIBLE" else styles["VerdictManualReview"])
            )
            final_s = (
                styles["VerdictEligible"] if be.final_decision_state.value == "ELIGIBLE"
                else (styles["VerdictNotEligible"] if be.final_decision_state.value == "NOT_ELIGIBLE" else styles["VerdictManualReview"])
            )
            issue_count = (
                be.missing_evidence_count
                + be.conflicting_evidence_count
                + be.ambiguous_evidence_count
                + be.unreadable_evidence_count
            )

            matrix_rows.append([
                Paragraph(str(idx), styles["TableCell"]),
                Paragraph(be.bidder_name, styles["BodyBold"]),
                Paragraph(be.automated_overall_result.value, auto_s),
                Paragraph(be.human_overall_decision.value if be.human_overall_decision else "None", styles["TableCell"]),
                Paragraph(be.final_decision_state.value, final_s),
                Paragraph(f"{be.mandatory_eligible_count} / {be.mandatory_criteria_count}", styles["TableCell"]),
                Paragraph(f"Reviews: {be.manual_review_count}<br/>Issues: {issue_count}", styles["TableCell"]),
            ])

        matrix_table = Table(matrix_rows, colWidths=[20, 120, 70, 74, 70, 70, 80])
        matrix_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2B6CB0")),
                ("PADDING", (0, 0), (-1, -1), 4),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E2E8F0")),
            ])
        )
        elements.append(matrix_table)
        elements.append(Spacer(1, 8))

        # SECTION C: AUDIT & LINEAGE SUMMARY
        if audit_summary:
            elements.append(Paragraph("SECTION C - SYSTEM AUDIT & PROVENANCE SUMMARY", styles["SectionHeader"]))
            audit_rows = [
                [
                    Paragraph("<b>Timestamp</b>", styles["TableHead"]),
                    Paragraph("<b>Action</b>", styles["TableHead"]),
                    Paragraph("<b>Entity</b>", styles["TableHead"]),
                    Paragraph("<b>Actor</b>", styles["TableHead"]),
                    Paragraph("<b>Details / Reason</b>", styles["TableHead"]),
                ]
            ]
            for al in audit_summary[:15]:
                ts = al.get("timestamp", "")
                if isinstance(ts, str) and len(ts) > 19:
                    ts = ts[:19]
                audit_rows.append([
                    Paragraph(str(ts), styles["TableCell"]),
                    Paragraph(al.get("action", ""), styles["TableCell"]),
                    Paragraph(f"{al.get('entity_type', '')}:{al.get('entity_id', '')[:8]}", styles["TableCell"]),
                    Paragraph(str(al.get("actor_id", "SYSTEM"))[:12], styles["TableCell"]),
                    Paragraph(al.get("reason") or "-", styles["TableCell"]),
                ])
            audit_table = Table(audit_rows, colWidths=[85, 105, 84, 80, 150])
            audit_table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4A5568")),
                    ("PADDING", (0, 0), (-1, -1), 3),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E2E8F0")),
                ])
            )
            elements.append(audit_table)

        # Build PDF
        doc.build(elements, canvasmaker=NumberedCanvas)
        buffer.seek(0)
        return buffer.getvalue()
