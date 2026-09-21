"""Comparative Evaluation PDF Report Generator using ReportLab."""

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
from app.ranking.schemas import ComparativeEvaluationResponse


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
        self.drawString(54, 750, "CRPF PROCUREMENT EVALUATION PLATFORM - COMPARATIVE RANKING REPORT")
        self.drawRightString(558, 750, "OFFICIAL PROCUREMENT RECORD")
        self.setStrokeColor(colors.HexColor("#CBD5E0"))
        self.setLineWidth(0.5)
        self.line(54, 744, 558, 744)

        # Bottom Footer
        self.line(54, 45, 558, 45)
        self.drawString(54, 34, "CRPF Multi-Bidder Evaluation & Ranking Engine | Deterministic Audit Artifact")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 34, page_str)
        self.restoreState()


def generate_comparative_ranking_pdf(
    ranking_data: ComparativeEvaluationResponse,
    tender_number: str = "CRPF/PPE/2026/001",
    tender_title: str = "Supply of Advanced Personal Protective Equipment",
) -> bytes:
    """Generate official government-style comparative evaluation PDF report."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#1A365D"),
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=14,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#2B6CB0"),
        spaceAfter=12,
    )
    h2_style = ParagraphStyle(
        "SectionH2",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#1A202C"),
        spaceBefore=10,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "BodyDark",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#2D3748"),
    )
    bold_cell_style = ParagraphStyle(
        "BoldCell",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#1A202C"),
    )
    badge_l1 = ParagraphStyle(
        "BadgeL1",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#22543D"),
    )
    badge_ineligible = ParagraphStyle(
        "BadgeIneligible",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#742A2A"),
    )

    story = []

    # Title
    story.append(Paragraph("CENTRAL RESERVE POLICE FORCE (CRPF)", title_style))
    story.append(
        Paragraph("MULTI-BIDDER COMPARATIVE EVALUATION & RANKING REPORT", subtitle_style)
    )

    # Section A: Tender & Methodology Details
    story.append(Paragraph("SECTION A - TENDER & EVALUATION METHODOLOGY", h2_style))

    info_data = [
        [
            Paragraph("<b>Tender Number:</b>", body_style),
            Paragraph(tender_number, bold_cell_style),
            Paragraph("<b>Tender Version:</b>", body_style),
            Paragraph(f"v1 (Run ID: {str(ranking_data.evaluation_run_id)[:8]}...)", body_style),
        ],
        [
            Paragraph("<b>Tender Title:</b>", body_style),
            Paragraph(tender_title, body_style),
            Paragraph("<b>Evaluation Date:</b>", body_style),
            Paragraph(ranking_data.evaluation_date.strftime("%Y-%m-%d %H:%M:%S UTC"), body_style),
        ],
        [
            Paragraph("<b>Evaluation Method:</b>", body_style),
            Paragraph(f"<b>{ranking_data.evaluation_method.value if hasattr(ranking_data.evaluation_method, 'value') else ranking_data.evaluation_method}</b>", bold_cell_style),
            Paragraph("<b>Tie-Breaker Rule:</b>", body_style),
            Paragraph("HUMAN PROCUREMENT COMMITTEE REVIEW", body_style),
        ],
    ]
    info_table = Table(info_data, colWidths=[100, 152, 100, 152])
    info_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7FAFC")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ])
    )
    story.append(info_table)
    story.append(Spacer(1, 10))

    # Section B: Executive Summary Counts
    story.append(Paragraph("SECTION B - PARTICIPATION & QUALIFICATION SUMMARY", h2_style))

    summary_data = [
        [
            Paragraph("<b>Total Bidders</b>", TA_CENTER_style(bold_cell_style)),
            Paragraph("<b>Mandatory Eligible</b>", TA_CENTER_style(bold_cell_style)),
            Paragraph("<b>Not Eligible</b>", TA_CENTER_style(bold_cell_style)),
            Paragraph("<b>Under Review</b>", TA_CENTER_style(bold_cell_style)),
            Paragraph("<b>Ranked in Pool</b>", TA_CENTER_style(bold_cell_style)),
        ],
        [
            Paragraph(f"<b>{ranking_data.total_bidders}</b>", TA_CENTER_style(bold_cell_style)),
            Paragraph(f"<font color='#2F855A'><b>{ranking_data.eligible_count}</b></font>", TA_CENTER_style(bold_cell_style)),
            Paragraph(f"<font color='#C53030'><b>{ranking_data.not_eligible_count}</b></font>", TA_CENTER_style(bold_cell_style)),
            Paragraph(f"<font color='#DD6B20'><b>{ranking_data.manual_review_count}</b></font>", TA_CENTER_style(bold_cell_style)),
            Paragraph(f"<font color='#2B6CB0'><b>{ranking_data.ranked_count}</b></font>", TA_CENTER_style(bold_cell_style)),
        ],
    ]
    sum_table = Table(summary_data, colWidths=[100, 101, 101, 101, 101])
    sum_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDF2F7")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ])
    )
    story.append(sum_table)
    story.append(Spacer(1, 12))

    # Section C: Comparative Ranking Table
    story.append(Paragraph("SECTION C - COMPARATIVE RANKING & STANDING", h2_style))

    table_headers = [
        Paragraph("<b>Rank</b>", bold_cell_style),
        Paragraph("<b>Bidder Name</b>", bold_cell_style),
        Paragraph("<b>Eligibility</b>", bold_cell_style),
        Paragraph("<b>Evaluated Price</b>", bold_cell_style),
        Paragraph("<b>Score</b>", bold_cell_style),
        Paragraph("<b>Standing / Status</b>", bold_cell_style),
    ]
    rank_rows = [table_headers]

    for item in ranking_data.rankings:
        # Format Rank Label
        if item.rank_label:
            rank_p = Paragraph(f"<b>{item.rank_label}</b>", badge_l1 if "L1" in item.rank_label or "H1" in item.rank_label else bold_cell_style)
        elif item.rank:
            rank_p = Paragraph(f"#{item.rank}", bold_cell_style)
        else:
            rank_p = Paragraph("-", body_style)

        # Format Price
        if item.evaluated_price is not None:
            price_str = f"INR {item.evaluated_price:,.2f}"
        else:
            price_str = "N/A"

        # Format Score
        if item.combined_score is not None:
            score_str = f"{item.combined_score:.2f}"
        elif item.technical_score is not None:
            score_str = f"Tech: {item.technical_score:.1f}"
        else:
            score_str = "-"

        # Status style
        if item.ranking_status.value == "QUALIFIED_RANKED":
            status_p = Paragraph("<font color='#276749'><b>QUALIFIED_RANKED</b></font>", body_style)
        elif item.ranking_status.value == "EXCLUDED_INELIGIBLE":
            status_p = Paragraph("<font color='#9B2C2C'><b>EXCLUDED (INELIGIBLE)</b></font>", body_style)
        elif item.ranking_status.value == "PENDING_MANUAL_REVIEW":
            status_p = Paragraph("<font color='#C05621'><b>PENDING REVIEW</b></font>", body_style)
        elif item.ranking_status.value == "TIE_REQUIRES_HUMAN_REVIEW":
            status_p = Paragraph("<font color='#805AD5'><b>TIE - COMMITTEE ACTION</b></font>", body_style)
        else:
            status_p = Paragraph(item.ranking_status.value, body_style)

        rank_rows.append([
            rank_p,
            Paragraph(f"<b>{item.bidder_name}</b>", body_style),
            Paragraph(str(item.eligibility_status.value if hasattr(item.eligibility_status, 'value') else item.eligibility_status), body_style),
            Paragraph(price_str, body_style),
            Paragraph(score_str, body_style),
            status_p,
        ])

    comp_table = Table(rank_rows, colWidths=[54, 150, 80, 90, 40, 90])
    comp_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2B6CB0")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#A0AEC0")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ])
    )
    story.append(comp_table)
    story.append(Spacer(1, 15))

    # Section D: Committee Review & Final Award Notice
    story.append(Paragraph("SECTION D - PROCUREMENT COMMITTEE REVIEW & FINAL AWARD", h2_style))
    disclaimer_text = (
        "<b>LEGAL & COMPLIANCE MANDATE:</b> This comparative ranking is calculated strictly deterministically "
        "by the platform rule engine using validated inputs and tender criteria. The system explains and ranks; "
        "it does NOT make the procurement award decision. The final award decision remains exclusively with the "
        "duly authorized Central Reserve Police Force (CRPF) Tender Procurement Committee."
    )
    story.append(Paragraph(disclaimer_text, body_style))
    story.append(Spacer(1, 15))

    # Sign-off boxes
    sig_data = [
        [
            Paragraph("<b>Evaluated By:</b><br/><br/>___________________________<br/>System Audit Officer", body_style),
            Paragraph("<b>Reviewed By:</b><br/><br/>___________________________<br/>Member, Technical Committee", body_style),
            Paragraph("<b>Approved By:</b><br/><br/>___________________________<br/>Chairman, Procurement Board", body_style),
        ]
    ]
    sig_table = Table(sig_data, colWidths=[168, 168, 168])
    sig_table.setStyle(
        TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7FAFC")),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ])
    )
    story.append(sig_table)

    doc.build(story, canvasmaker=NumberedCanvas)
    return buffer.getvalue()


def TA_CENTER_style(base_style: ParagraphStyle) -> ParagraphStyle:
    """Helper to center-align a paragraph style."""
    s = ParagraphStyle("CenteredStyle", parent=base_style, alignment=TA_CENTER)
    return s
