from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from io import BytesIO
import re
from reportlab.lib import colors

def create_pdf_bytes(markdown_text: str) -> BytesIO:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            rightMargin=72, leftMargin=72,
                            topMargin=72, bottomMargin=18)
    
    styles = getSampleStyleSheet()
    
    # High-contrast, print-friendly styles for exported notes.
    title_style = ParagraphStyle(
        'ExportTitle',
        parent=styles['Heading1'],
        alignment=1,
        textColor=colors.HexColor('#111111'),
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        spaceAfter=14,
    )

    heading_style = ParagraphStyle(
        'ExportHeading',
        parent=styles['Heading2'],
        textColor=colors.HexColor('#111111'),
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=19,
        spaceBefore=10,
        spaceAfter=7,
    )

    normal_style = ParagraphStyle(
        'ExportBody',
        parent=styles['Normal'],
        textColor=colors.HexColor('#222222'),
        fontName='Helvetica',
        fontSize=12,
        leading=17,
        spaceAfter=6,
    )

    bullet_style = ParagraphStyle(
        'ExportBullet',
        parent=normal_style,
        leftIndent=16,
        firstLineIndent=-10,
        bulletIndent=0,
        spaceAfter=5,
    )
    
    # Very basic markdown parser for the PDF
    content = []
    
    # Add title
    content.append(Paragraph("AI Life Dashboard Export", title_style))
    content.append(Spacer(1, 0.2 * inch))
    
    lines = markdown_text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            content.append(Spacer(1, 0.1 * inch))
            continue
            
        # Clean up some basic markdown
        # Convert **bold** to <b>bold</b>
        line = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', line)
        
        if line.startswith('# '):
            content.append(Paragraph(line[2:], title_style))
        elif line.startswith('## '):
            content.append(Paragraph(line[3:], heading_style))
        elif line.startswith('### '):
            content.append(Paragraph(line[4:], heading_style))
        elif line.startswith('- ') or line.startswith('* '):
            # Bullet point
            content.append(Paragraph("• " + line[2:], bullet_style))
        else:
            content.append(Paragraph(line, normal_style))
            
    doc.build(content)
    buffer.seek(0)
    return buffer
