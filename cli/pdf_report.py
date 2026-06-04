"""PDF report generation using ReportLab.

Generates professional A4 PDF reports with:
- Title page with metadata
- Module summary pages with charts
- Complete test results table (paginated)

Uses non-vibrant color scheme and Helvetica font family.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Table,
    TableStyle,
    PageBreak,
    Spacer,
    Image,
)
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Non-vibrant color palette
COLORS = {
    'primary': colors.HexColor('#2c5f8d'),    # Muted blue
    'secondary': colors.HexColor('#5a7d92'),  # Slate blue
    'accent': colors.HexColor('#7a9c5e'),     # Muted green
    'warning': colors.HexColor('#c9a35d'),    # Muted gold
    'danger': colors.HexColor('#c47b7b'),     # Muted red
    'neutral': colors.HexColor('#6b7b8c'),    # Gray
    'background': colors.HexColor('#f5f7f8'), # Light gray
    'text': colors.HexColor('#333333'),       # Dark gray for text
    'light_text': colors.HexColor('#666666'), # Lighter gray
    'border': colors.HexColor('#dddddd'),     # Light border
}

# Risk level colors
RISK_COLORS = {
    'safe': colors.HexColor('#e0e0e0'),       # Light gray
    'ambiguous': colors.HexColor('#fff9c4'),  # Light yellow
    'low': colors.HexColor('#c8e6c9'),        # Light green
    'moderate': colors.HexColor('#ffe0b2'),   # Orange
    'high': colors.HexColor('#ef9a9a'),       # Muted red
}


def get_risk_color(score: float):
    """Get color for risk score."""
    if score < 0.20:
        return RISK_COLORS['safe']
    elif score < 0.21:
        return RISK_COLORS['ambiguous']
    elif score < 0.40:
        return RISK_COLORS['low']
    elif score < 0.70:
        return RISK_COLORS['moderate']
    else:
        return RISK_COLORS['high']


def get_risk_label(score: float) -> str:
    """Get label for risk score."""
    if score < 0.20:
        return "Safe"
    elif score < 0.21:
        return "Ambiguous"
    elif score < 0.40:
        return "Low Risk"
    elif score < 0.70:
        return "Moderate Risk"
    else:
        return "High Risk"


class PDFReportGenerator:
    """Generate PDF reports from AIGuard evaluation data."""

    def __init__(self, output_path: Path):
        self.output_path = Path(output_path)
        self.doc = SimpleDocTemplate(
            str(self.output_path),
            pagesize=A4,
            leftMargin=2*cm,
            rightMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm,
        )
        self.styles = getSampleStyleSheet()
        self.page_num = 0
        self.total_pages = 0
        
        # Configure fonts
        self._configure_fonts()
        
    def _configure_fonts(self):
        """Configure Helvetica fonts (already built into PDF)."""
        # Helvetica is built-in, no registration needed
        self.title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=COLORS['primary'],
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
        )
        
        self.heading_style = ParagraphStyle(
            'CustomHeading',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=COLORS['text'],
            spaceAfter=12,
            spaceBefore=12,
            fontName='Helvetica-Bold',
        )
        
        self.subheading_style = ParagraphStyle(
            'CustomSubheading',
            parent=self.styles['Heading3'],
            fontSize=12,
            textColor=COLORS['neutral'],
            spaceAfter=6,
            spaceBefore=6,
            fontName='Helvetica-Bold',
        )
        
        self.body_style = ParagraphStyle(
            'CustomBody',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=COLORS['text'],
            leading=14,
            fontName='Helvetica',
        )
        
        self.small_style = ParagraphStyle(
            'CustomSmall',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=COLORS['light_text'],
            leading=10,
            fontName='Helvetica',
        )

    def generate(self, report_data: Dict[str, Any]) -> Path:
        """Generate complete PDF from report data."""
        story = []
        
        # Title page
        story.extend(self._build_title_page(report_data))
        story.append(PageBreak())
        
        # Module summaries
        for module in report_data.get('modules', []):
            story.extend(self._build_module_summary(module))
            story.append(PageBreak())
        
        # Test results (all modules combined)
        all_results = []
        for module in report_data.get('modules', []):
            all_results.extend(module.get('results', []))
        
        if all_results:
            story.extend(self._build_test_results_table(all_results))
        
        # Build PDF
        self.doc.build(
            story,
            onFirstPage=self._add_header_footer,
            onLaterPages=self._add_header_footer,
        )
        
        return self.output_path

    def _build_title_page(self, report: Dict[str, Any]) -> List:
        """Build title page with metadata."""
        elements = []
        
        # Spacing
        elements.append(Spacer(1, 3*cm))
        
        # Title
        title = Paragraph("AIGuard Evaluation Report", self.title_style)
        elements.append(title)
        
        elements.append(Spacer(1, 2*cm))
        
        # Metadata table
        metadata = [
            ['Project:', report.get('project', 'N/A')],
            ['Date:', report.get('timestamp', datetime.now(timezone.utc).isoformat())],
            ['Status:', report.get('status', 'unknown').upper()],
            ['Exit Code:', str(report.get('exit_code', 'N/A'))],
            ['Version:', report.get('aiguard_version', 'unknown')],
        ]
        
        meta_table = Table(metadata, colWidths=[4*cm, 8*cm])
        meta_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('TEXTCOLOR', (0, 0), (0, -1), COLORS['neutral']),
            ('TEXTCOLOR', (1, 0), (-1, -1), COLORS['text']),
        ]))
        
        elements.append(meta_table)
        elements.append(Spacer(1, 5*cm))
        
        # Summary stats
        modules = report.get('modules', [])
        total_tests = sum(m.get('total_tests', 0) for m in modules)
        failed_tests = sum(m.get('failed_tests', 0) for m in modules)
        
        if total_tests > 0:
            summary_data = [
                ['Total Tests:', str(total_tests)],
                ['Failed Tests:', str(failed_tests)],
                ['Pass Rate:', f"{((total_tests - failed_tests) / total_tests * 100):.1f}%"],
            ]
            
            summary_table = Table(summary_data, colWidths=[4*cm, 4*cm])
            summary_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 12),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BACKGROUND', (0, 0), (-1, -1), COLORS['background']),
                ('TEXTCOLOR', (1, 0), (-1, -1), COLORS['primary']),
            ]))
            
            elements.append(summary_table)
        
        return elements

    def _build_module_summary(self, module: Dict[str, Any]) -> List:
        """Build module summary page with stats and charts."""
        elements = []
        
        # Module heading
        module_name = module.get('module', 'Unknown Module')
        elements.append(Paragraph(f"Module: {module_name}", self.heading_style))
        elements.append(Spacer(1, 1*cm))
        
        # Stats table
        stats = [
            ['Total Tests:', str(module.get('total_tests', 0))],
            ['Failed Tests:', str(module.get('failed_tests', 0))],
            ['Risk Score:', f"{module.get('global_risk_score', 0):.4f}"],
            ['Threshold:', str(module.get('threshold', 'N/A'))],
        ]
        
        stats_table = Table(stats, colWidths=[4*cm, 4*cm])
        stats_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BACKGROUND', (0, 0), (-1, -1), COLORS['background']),
            ('TEXTCOLOR', (1, 0), (-1, -1), COLORS['text']),
        ]))
        
        elements.append(stats_table)
        elements.append(Spacer(1, 1.5*cm))
        
        # Risk distribution chart
        elements.append(Paragraph("Risk Score Distribution", self.subheading_style))
        risk_chart = self._create_risk_chart(module.get('results', []))
        elements.append(risk_chart)
        elements.append(Spacer(1, 1*cm))
        
        # Pass/Fail breakdown
        elements.append(Paragraph("Pass/Fail Breakdown", self.subheading_style))
        pass_fail_chart = self._create_pass_fail_chart(module.get('results', []))
        elements.append(pass_fail_chart)
        elements.append(Spacer(1, 1*cm))
        
        # Category breakdown
        elements.append(Paragraph("Category Breakdown", self.subheading_style))
        category_chart = self._create_category_chart(module.get('failure_breakdown_by_category', {}))
        elements.append(category_chart)
        
        return elements

    def _create_risk_chart(self, results: List[Dict]) -> Drawing:
        """Create risk distribution bar chart."""
        # Count scores by range
        bins = {'safe': 0, 'ambiguous': 0, 'low': 0, 'moderate': 0, 'high': 0}
        
        for result in results:
            score = result.get('risk_score', 0)
            if score < 0.20:
                bins['safe'] += 1
            elif score < 0.21:
                bins['ambiguous'] += 1
            elif score < 0.40:
                bins['low'] += 1
            elif score < 0.70:
                bins['moderate'] += 1
            else:
                bins['high'] += 1
        
        # Create bar chart
        chart = VerticalBarChart()
        chart.width = 12*cm
        chart.height = 6*cm
        chart.x = 2*cm
        chart.y = 4*cm
        
        chart.xValueAxis.labels.fontName = 'Helvetica'
        chart.xValueAxis.labels.fontSize = 8
        chart.yValueAxis.labels.fontName = 'Helvetica'
        chart.yValueAxis.labels.fontSize = 8
        
        categories = ['Safe', 'Ambiguous', 'Low', 'Moderate', 'High']
        values = [bins['safe'], bins['ambiguous'], bins['low'], bins['moderate'], bins['high']]
        
        chart.data = [values]
        chart.bars[0].strokeColor = colors.white
        chart.bars[0].strokeWidth = 0
        
        # Color bars
        for i, color in enumerate([
            RISK_COLORS['safe'],
            RISK_COLORS['ambiguous'],
            RISK_COLORS['low'],
            RISK_COLORS['moderate'],
            RISK_COLORS['high'],
        ]):
            chart.bars[i].fillColor = color
        
        return chart

    def _create_pass_fail_chart(self, results: List[Dict]) -> Drawing:
        """Create pass/fail pie chart."""
        passed = sum(1 for r in results if r.get('status') == 'PASS')
        failed = len(results) - passed
        
        pie = Pie()
        pie.width = 8*cm
        pie.height = 6*cm
        pie.x = 3*cm
        pie.y = 4*cm
        
        pie.data = [passed, failed]
        pie.labels = ['Passed', 'Failed']
        pie.slices.strokeWidth = 0.5
        
        pie.slices[0].fillColor = COLORS['accent']
        pie.slices[1].fillColor = COLORS['danger']
        
        return pie

    def _create_category_chart(self, breakdown: Dict[str, Any]) -> Drawing:
        """Create category breakdown horizontal bar chart."""
        if not breakdown:
            # Empty placeholder
            from reportlab.platypus import Paragraph
            return Paragraph("No category data", self.small_style)
        
        # Sort by count
        sorted_cats = sorted(breakdown.items(), key=lambda x: x[1], reverse=True)[:10]
        
        chart = VerticalBarChart()
        chart.width = 12*cm
        chart.height = min(6*cm, len(sorted_cats) * 0.6*cm)
        chart.x = 2*cm
        chart.y = 4*cm
        
        categories = [cat[:20] + '...' if len(cat) > 20 else cat for cat, _ in sorted_cats]
        values = [count for _, count in sorted_cats]
        
        chart.data = [values]
        chart.bars[0].fillColor = COLORS['primary']
        chart.bars[0].strokeColor = colors.white
        chart.bars[0].strokeWidth = 0
        
        return chart

    def _build_test_results_table(self, results: List[Dict]) -> List:
        """Build paginated test results table."""
        elements = []
        
        elements.append(Paragraph("All Test Results", self.heading_style))
        elements.append(Spacer(1, 0.5*cm))
        
        # Table header
        header = [['ID', 'Category', 'Risk Score', 'Status', 'Rationale']]
        header_table = Table(header, colWidths=[1.5*cm, 4*cm, 2*cm, 2*cm, 6*cm])
        header_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TEXTCOLOR', (0, 0), (-1, -1), COLORS['text']),
            ('BACKGROUND', (0, 0), (-1, -1), COLORS['primary']),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
        ]))
        
        elements.append(header_table)
        elements.append(Spacer(1, 0.2*cm))
        
        # Table rows (paginated at 50 per page)
        rows_per_page = 50
        for i in range(0, len(results), rows_per_page):
            if i > 0:
                elements.append(PageBreak())
                elements.append(header_table)  # Repeat header
                elements.append(Spacer(1, 0.2*cm))
            
            chunk = results[i:i + rows_per_page]
            rows = []
            
            for idx, result in enumerate(chunk, start=i + 1):
                risk_score = result.get('risk_score', 0)
                status = result.get('status', 'UNKNOWN')
                rationale = result.get('rationale', 'N/A')[:50]
                
                row = [
                    str(idx),
                    (result.get('category', 'N/A') or 'N/A')[:20],
                    f"{risk_score:.4f}",
                    status,
                    rationale,
                ]
                rows.append(row)
            
            if rows:
                result_table = Table(rows, colWidths=[1.5*cm, 4*cm, 2*cm, 2*cm, 6*cm])
                result_table.setStyle(TableStyle([
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 8),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 3),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 3),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('GRID', (0, 0), (-1, -1), 0.5, COLORS['border']),
                ]))
                
                elements.append(result_table)
        
        return elements

    def _add_header_footer(self, canvas, doc):
        """Add header and footer to each page."""
        # Header
        canvas.saveState()
        canvas.setFont('Helvetica-Bold', 10)
        canvas.setFillColor(COLORS['primary'])
        canvas.drawString(2*cm, 27.5*cm, "AIGuard Evaluation Report")
        canvas.restoreState()
        
        # Footer with page number
        canvas.saveState()
        canvas.setFont('Helvetica', 9)
        canvas.setFillColor(COLORS['light_text'])
        
        # Calculate total pages
        self.total_pages = doc.page
        
        page_info = f"Page {doc.page} of {self.total_pages}"
        canvas.drawRightString(18*cm, 1*cm, page_info)
        canvas.restoreState()
