from io import BytesIO
from xml.sax.saxutils import escape


def build_invoice_pdf(order, items, customer_email):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.graphics.barcode import code128
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='InvoiceTitle', parent=styles['Title'], fontName='Helvetica-Bold', fontSize=24, textColor=colors.HexColor('#1e2420'), spaceAfter=8))
    styles.add(ParagraphStyle(name='SmallMuted', parent=styles['Normal'], fontSize=9, leading=13, textColor=colors.HexColor('#777777')))
    styles.add(ParagraphStyle(name='Right', parent=styles['Normal'], alignment=TA_RIGHT, fontSize=10))
    buffer = BytesIO()
    def draw_header(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(colors.HexColor('#1e2420'))
        canvas.setFont('Helvetica-Bold', 17)
        canvas.drawString(20 * mm, A4[1] - 14 * mm, 'phoneCase254')
        canvas.setFillColor(colors.HexColor('#777777'))
        canvas.setFont('Helvetica', 8)
        canvas.drawRightString(A4[0] - 20 * mm, A4[1] - 13.5 * mm, 'ORDER INVOICE')
        canvas.restoreState()

    document = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20 * mm, leftMargin=20 * mm, topMargin=28 * mm, bottomMargin=18 * mm)
    story = [
        Paragraph(f'ORDER INVOICE {order.public_reference}', styles['SmallMuted']),
        Spacer(1, 12),
        code128.Code128(order.public_reference, barHeight=14 * mm, barWidth=0.38 * mm, humanReadable=True),
        Spacer(1, 14),
        Paragraph(f'<b>Customer</b><br/>{order.full_name}<br/>{customer_email}<br/>{order.phone}<br/>{order.delivery_address}', styles['Normal']),
        Spacer(1, 18),
    ]
    rows = [[Paragraph('<b>Item</b>', styles['Normal']), Paragraph('<b>Qty</b>', styles['Normal']), Paragraph('<b>Amount</b>', styles['Right'])]]
    for item in items:
        product = item['product']
        category = product.category.name if product.category else 'Phone case'
        details = f'<b>{escape(product.name)}</b><br/><font color="#777777">{escape(category)}</font><br/>{escape(product.description)}'
        rows.append([Paragraph(details, styles['Normal']), str(item['quantity']), Paragraph(f'KSh {item["line_total"]:,.2f}', styles['Right'])])
    table = Table(rows, colWidths=[110 * mm, 20 * mm, 40 * mm])
    table.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#dddddd')), ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f4f2ed')), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('LEFTPADDING', (0, 0), (-1, -1), 8), ('RIGHTPADDING', (0, 0), (-1, -1), 8), ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 8)]))
    story.extend([table, Spacer(1, 18)])
    totals = [['Subtotal', f'KSh {order.subtotal:,.2f}']]
    if order.item_discount:
        totals.append(['Item discount (5%)', f'- KSh {order.item_discount:,.2f}'])
    if order.delivery_discount:
        totals.append(['Delivery discount', f'- KSh {order.delivery_discount:,.2f}'])
    if order.points_discount:
        totals.append([f'Loyalty points ({order.points_redeemed})', f'- KSh {order.points_discount:,.2f}'])
    totals.extend([['Delivery', f'KSh {order.delivery_fee:,.2f}'], ['TOTAL', f'KSh {order.total:,.2f}']])
    totals_table = Table(totals, colWidths=[110 * mm, 60 * mm], hAlign='RIGHT')
    totals_table.setStyle(TableStyle([('ALIGN', (1, 0), (1, -1), 'RIGHT'), ('LINEABOVE', (0, -1), (-1, -1), 1, colors.HexColor('#1e2420')), ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'), ('FONTSIZE', (0, -1), (-1, -1), 13), ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6)]))
    story.extend([totals_table, Spacer(1, 20), Paragraph('Thank you for shopping with phoneCase254. Keep this invoice for your records.', styles['SmallMuted'])])
    document.build(story, onFirstPage=draw_header, onLaterPages=draw_header)
    return buffer.getvalue()
