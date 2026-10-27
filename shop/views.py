from decimal import Decimal
import io
import json
import mimetypes
import requests
import os
import zipfile
from xml.sax.saxutils import escape
from datetime import timedelta
from django.conf import settings
import logging

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives, send_mail
from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.http import FileResponse, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils import timezone
from django.contrib.auth.tokens import default_token_generator
from .forms import CheckoutForm, ContactForm, DashboardJobForm, DashboardOfferForm, DashboardProductForm, JobApplicationForm, ProductReviewForm, SignUpForm
from .models import Category, ContactMessage, CustomerProfile, JobApplication, JobPosting, Order, OrderItem, Product, ProductReview, Wishlist
from .services.mpesa import initiate_stk_push, query_stk_push
from .services.invoice import build_invoice_pdf

logger = logging.getLogger(__name__)
DELIVERY_RATE = Decimal('0.10')
# STK query responses can be temporary; only these known codes are terminal failures.
MPESA_QUERY_TERMINAL_FAILURE_CODES = {'1', '1032', '1037', '2001', '2006'}
PREPAID_ITEM_DISCOUNT_RATE = Decimal('0.05')
PREPAID_DELIVERY_DISCOUNT_RATE = Decimal('0.06')
WELCOME_POINTS = 50
REVIEW_POINTS = 25
FREE_DELIVERY_DISCOUNT_THRESHOLD = Decimal('2000')

staff_required = user_passes_test(lambda user: user.is_active and user.is_staff, login_url='login')

@staff_required
def dashboard(request):
    today = timezone.localdate()
    start_of_month = today.replace(day=1)
    orders = Order.objects.filter(payment_status__in=['paid', 'on_delivery']).select_related('user').prefetch_related('items__product')
    paid_orders = orders.filter(payment_status='paid')
    recent_orders = orders.order_by('-created_at')[:6]
    low_stock = Product.objects.filter(stock__lte=5).order_by('stock', 'name')
    out_of_stock_count = Product.objects.filter(stock=0).count()
    top_products = Product.objects.annotate(
        units_sold=Sum('orderitem__quantity', filter=Q(orderitem__order__payment_status='paid'))
    ).order_by('-units_sold', 'name')[:5]
    movement_since = timezone.now() - timedelta(days=30)
    movement_products = list(Product.objects.annotate(units_sold_30d=Sum('orderitem__quantity', filter=Q(orderitem__order__payment_status='paid', orderitem__order__created_at__gte=movement_since))).order_by('-units_sold_30d', 'name'))
    movement_fast = [product for product in movement_products if (product.units_sold_30d or 0) >= 10][:5]
    movement_slow = [product for product in movement_products if 0 < (product.units_sold_30d or 0) < 10][:5]
    movement_death = [product for product in movement_products if not product.units_sold_30d and product.stock > 0][:5]
    recent_customers = User.objects.filter(is_staff=False).order_by('-date_joined')[:5]
    month_orders = orders.filter(created_at__date__gte=start_of_month)
    month_paid_orders = paid_orders.filter(created_at__date__gte=start_of_month)
    sales_series = []
    for days_ago in range(89, -1, -1):
        sale_date = today - timedelta(days=days_ago)
        daily = paid_orders.filter(created_at__date=sale_date).aggregate(total=Sum('total'), orders=Count('id'))
        sales_series.append({'date': sale_date.strftime('%b %d').replace(' 0', ' '), 'sales': float(daily['total'] or 0), 'orders': daily['orders'] or 0})
    month_revenue = month_paid_orders.aggregate(total=Sum('total'))['total'] or Decimal('0')
    total_revenue = paid_orders.aggregate(total=Sum('total'))['total'] or Decimal('0')
    status_counts = {key: orders.filter(status=key).count() for key, label in Order.STATUS_CHOICES}
    stock_total = Product.objects.aggregate(total=Sum('stock'))['total'] or 0
    inventory_value = Product.objects.aggregate(total=Sum(F('price') * F('stock')))['total'] or Decimal('0')
    activity = []
    for order in orders.order_by('-created_at')[:3]:
        activity.append({'kind': 'order', 'label': 'New order', 'detail': order.public_reference, 'time': order.created_at})
    for customer in recent_customers[:2]:
        activity.append({'kind': 'customer', 'label': 'New customer', 'detail': customer.get_full_name() or customer.username, 'time': customer.date_joined})
    activity.sort(key=lambda item: item['time'], reverse=True)
    return render(request, 'shop/dashboard.html', {
        'today': today,
        'total_orders': orders.count(),
        'month_orders': month_orders.count(),
        'total_revenue': total_revenue,
        'month_revenue': month_revenue,
        'total_customers': User.objects.filter(is_staff=False).count(),
        'product_count': Product.objects.count(),
        'low_stock_count': low_stock.count(),
        'out_of_stock_count': out_of_stock_count,
        'healthy_stock_count': max(Product.objects.count() - low_stock.count(), 0),
        'low_stock': low_stock[:6],
        'recent_orders': recent_orders,
        'top_products': top_products,
        'recent_customers': recent_customers,
        'status_counts': status_counts,
        'stock_total': stock_total,
        'inventory_value': inventory_value,
        'activity': activity[:6],
        'sales_series': sales_series,
        'job_count': JobPosting.objects.filter(is_published=True).count(),
        'application_count': JobApplication.objects.count(),
        'movement_fast': movement_fast,
        'movement_slow': movement_slow,
        'movement_death': movement_death,
    })

@staff_required
def dashboard_report_export(request):
    report_rows = list(Order.objects.filter(payment_status__in=['paid', 'on_delivery']).select_related('user').order_by('-created_at'))
    export_format = request.GET.get('format', 'csv').lower()
    if export_format == 'pdf':
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
        output = io.BytesIO()
        document = SimpleDocTemplate(output, pagesize=landscape(A4), rightMargin=28, leftMargin=28, topMargin=28, bottomMargin=28)
        styles = getSampleStyleSheet()
        data = [['Order', 'Customer', 'Payment', 'Status', 'Total', 'Created']]
        data += [[o.public_reference, o.full_name, o.get_payment_status_display(), o.get_status_display(), f'KSh {o.total:,.0f}', o.created_at.strftime('%d %b %Y %H:%M')] for o in report_rows]
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#123c70')), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white), ('GRID', (0, 0), (-1, -1), .25, colors.HexColor('#d9e2ef')), ('FONTSIZE', (0, 0), (-1, -1), 8), ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f4f8fc')])]))
        document.build([Paragraph('phoneCase254 sales report', styles['Title']), table])
        response = HttpResponse(output.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="phoneCase254-sales-report.pdf"'
        return response
    if export_format == 'xlsx':
        def cell(value, reference):
            return f'<c r="{reference}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'
        rows = [['Order', 'Customer', 'Email', 'Payment', 'Status', 'Total', 'Created']]
        rows += [[o.public_reference, o.full_name, o.user.email, o.get_payment_status_display(), o.get_status_display(), o.total, o.created_at.strftime('%Y-%m-%d %H:%M')] for o in report_rows]
        sheet_rows = ''.join(f'<row r="{row_number}">' + ''.join(cell(value, f'{column}{row_number}') for column, value in zip('ABCDEFG', values)) + '</row>' for row_number, values in enumerate(rows, 1))
        workbook_files = {'[Content_Types].xml': '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>', '_rels/.rels': '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>', 'xl/workbook.xml': '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Orders" sheetId="1" r:id="rId1"/></sheets></workbook>', 'xl/_rels/workbook.xml.rels': '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>', 'xl/worksheets/sheet1.xml': f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>{sheet_rows}</sheetData></worksheet>'}
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
            for filename, content in workbook_files.items(): archive.writestr(filename, content)
        response = HttpResponse(output.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="phoneCase254-sales-report.xlsx"'
        return response
    if export_format == 'xml':
        xml_rows = ''.join(f'<order><reference>{escape(o.public_reference)}</reference><customer>{escape(o.full_name)}</customer><email>{escape(o.user.email)}</email><payment>{escape(o.get_payment_status_display())}</payment><status>{escape(o.get_status_display())}</status><total>{o.total}</total><created>{o.created_at.isoformat()}</created></order>' for o in report_rows)
        response = HttpResponse(f'<?xml version="1.0" encoding="UTF-8"?><sales_report>{xml_rows}</sales_report>', content_type='application/xml')
        response['Content-Disposition'] = 'attachment; filename="phoneCase254-sales-report.xml"'
        return response
    if export_format == 'png':
        from PIL import Image, ImageDraw
        image = Image.new('RGB', (1200, max(420, 180 + len(report_rows) * 28)), '#071b35')
        draw = ImageDraw.Draw(image)
        draw.text((42, 30), 'phoneCase254 sales report', fill='#ffffff')
        draw.text((42, 65), f'{len(report_rows)} orders · KSh {sum((o.total for o in report_rows), Decimal("0")):,.0f}', fill='#54aaff')
        y = 120
        for order in report_rows:
            draw.text((42, y), f'{order.public_reference}   {order.full_name[:28]}   KSh {order.total:,.0f}   {order.get_status_display()}', fill='#dcecff')
            y += 28
        output = io.BytesIO(); image.save(output, format='PNG')
        response = HttpResponse(output.getvalue(), content_type='image/png')
        response['Content-Disposition'] = 'attachment; filename="phoneCase254-sales-report.png"'
        return response
    import csv
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="phoneCase254-sales-report.csv"'
    writer = csv.writer(response)
    writer.writerow(['Order reference', 'Customer', 'Email', 'Payment status', 'Order status', 'Subtotal', 'Delivery fee', 'Total', 'Created'])
    for order in report_rows:
        writer.writerow([order.public_reference, order.full_name, order.user.email, order.get_payment_status_display(), order.get_status_display(), order.subtotal, order.delivery_fee, order.total, order.created_at.strftime('%Y-%m-%d %H:%M')])
    return response

@staff_required
def dashboard_reports(request):
    report_orders = Order.objects.filter(payment_status__in=['paid', 'on_delivery']).select_related('user').order_by('-created_at')
    summary = report_orders.aggregate(total=Sum('total'), orders=Count('id'))
    return render(request, 'shop/dashboard_reports.html', {'report_orders': report_orders, 'report_total': summary['total'] or Decimal('0'), 'report_count': summary['orders'] or 0})

@staff_required
def dashboard_settings(request):
    return render(request, 'shop/dashboard_settings.html', {'mpesa_environment': settings.MPESA_ENVIRONMENT, 'callback_configured': settings.MPESA_CALLBACK_URL.startswith('https://') and 'your-public-domain' not in settings.MPESA_CALLBACK_URL, 'cloudinary_configured': bool(os.environ.get('CLOUDINARY_URL')), 'support_phone': settings.SUPPORT_PHONE, 'support_email': settings.SUPPORT_EMAIL})

@staff_required
def dashboard_search(request):
    query = request.GET.get('q', '').strip()
    products = Product.objects.none()
    orders = Order.objects.none()
    customers = User.objects.none()
    if query:
        products = Product.objects.filter(Q(name__icontains=query) | Q(description__icontains=query) | Q(category__name__icontains=query)).select_related('category')[:25]
        orders = Order.objects.filter(payment_status__in=['paid', 'on_delivery']).filter(Q(public_reference__icontains=query) | Q(full_name__icontains=query) | Q(phone__icontains=query) | Q(mpesa_receipt__icontains=query) | Q(user__email__icontains=query)).select_related('user').order_by('-created_at')[:25]
        customers = User.objects.filter(Q(username__icontains=query) | Q(first_name__icontains=query) | Q(last_name__icontains=query) | Q(email__icontains=query), is_staff=False)[:25]
    return render(request, 'shop/dashboard_search.html', {'query': query, 'products': products, 'orders': orders, 'customers': customers})

@staff_required
def dashboard_products(request):
    return render(request, 'shop/dashboard_list.html', {'section': 'Products', 'description': 'Manage your case catalogue, product photos, and offers.', 'products': Product.objects.select_related('category').order_by('name'), 'offer_choices': Product.OFFER_TYPES})

@staff_required
def dashboard_product_add(request):
    form = DashboardProductForm(request.POST or None, request.FILES or None)
    if form.is_valid():
        form.save()
        messages.success(request, 'Product added successfully.')
        return redirect('dashboard_products')
    return render(request, 'shop/dashboard_product_form.html', {'form': form})

@staff_required
def dashboard_jobs(request):
    return render(request, 'shop/dashboard_jobs.html', {'jobs': JobPosting.objects.all()})

@staff_required
def dashboard_job_applications(request):
    applications = JobApplication.objects.select_related('job').all()
    job_id = request.GET.get('job')
    if job_id and job_id.isdigit():
        applications = applications.filter(job_id=job_id)
    return render(request, 'shop/dashboard_job_applications.html', {'applications': applications})

@staff_required
def dashboard_application_resume(request, application_id):
    application = get_object_or_404(JobApplication, pk=application_id)
    if not application.resume:
        return HttpResponse('No CV attached.', status=404)
    if os.environ.get('CLOUDINARY_URL'):
        import cloudinary.utils
        public_id = application.resume.name
        if not public_id.startswith('media/'):
            public_id = f'media/{public_id}'
        file_format = os.path.splitext(application.resume.name)[1].lstrip('.').lower() or 'pdf'
        private_url = cloudinary.utils.private_download_url(public_id, file_format, resource_type='image', type='upload', secure=True, attachment=False)
        return redirect(private_url)
    response = FileResponse(application.resume.open('rb'), content_type=mimetypes.guess_type(application.resume.name)[0] or 'application/octet-stream')
    response['Content-Disposition'] = f'inline; filename="{os.path.basename(application.resume.name)}"'
    return response

@staff_required
def dashboard_job_add(request):
    form = DashboardJobForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, 'Job posting saved successfully.')
        return redirect('dashboard_jobs')
    return render(request, 'shop/dashboard_job_form.html', {'form': form})

@staff_required
@require_POST
def dashboard_offer_update(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    form = DashboardOfferForm(request.POST, instance=product)
    if form.is_valid():
        offer = form.save(commit=False)
        if offer.offer_type == 'none':
            offer.discount_percent = 0
            offer.offer_ends_at = None
        offer.save(update_fields=['offer_type', 'discount_percent', 'offer_ends_at'])
        messages.success(request, f'{product.name} offer updated.')
    else:
        messages.error(request, f'Offer could not be updated for {product.name}. Check the discount and end date.')
    return redirect(request.POST.get('next') or 'dashboard_products')

@staff_required
def dashboard_orders(request):
    return render(request, 'shop/dashboard_list.html', {'section': 'Orders', 'description': 'Review paid and pay-on-delivery purchases.', 'orders': Order.objects.filter(payment_status__in=['paid', 'on_delivery']).select_related('user').prefetch_related('items__product').order_by('-created_at'), 'status_choices': Order.STATUS_CHOICES})

@staff_required
@require_POST
def dashboard_order_status_update(request, order_id):
    order = get_object_or_404(Order, pk=order_id, payment_status__in=['paid', 'on_delivery'])
    new_status = request.POST.get('status', '')
    valid_statuses = {value for value, label in Order.STATUS_CHOICES}
    if new_status not in valid_statuses:
        messages.error(request, 'That order status is not valid.')
    elif new_status == order.status:
        messages.info(request, f'{order.public_reference} is already marked {order.get_status_display().lower()}.')
    else:
        was_on_delivery = order.payment_method == 'cod' and order.payment_status == 'on_delivery'
        order.status = new_status
        order.save(update_fields=['status', 'payment_status'])
        if new_status == 'delivered' and was_on_delivery and order.payment_status == 'paid':
            profile, _ = CustomerProfile.objects.get_or_create(user=order.user)
            profile.record_payment(order)
            order.status_updates.filter(status='cancelled').delete()
            messages.success(request, f'{order.public_reference} delivered and payment recorded as received.')
        else:
            messages.success(request, f'{order.public_reference} updated to {order.get_status_display()}.')
    return redirect(request.POST.get('next') or 'dashboard_orders')

@staff_required
def dashboard_customers(request):
    return render(request, 'shop/dashboard_list.html', {'section': 'Customers', 'description': 'View customer accounts, loyalty points, and order history.', 'customers': User.objects.filter(is_staff=False).order_by('-date_joined')})

@staff_required
def dashboard_inventory(request):
    return render(request, 'shop/dashboard_list.html', {'section': 'Inventory', 'description': 'Monitor stock levels and identify products that need attention.', 'inventory': Product.objects.select_related('category').order_by('stock', 'name')})

@staff_required
@require_POST
def dashboard_stock_update(request, product_id):
    try:
        change = int(request.POST.get('change', '0'))
    except (TypeError, ValueError):
        change = 0
    change = max(-1000, min(change, 1000))
    product = get_object_or_404(Product, pk=product_id)
    product.stock = max(0, product.stock + change)
    product.save(update_fields=['stock'])
    messages.success(request, f'{product.name} stock updated to {product.stock} units.')
    return redirect('dashboard_inventory')

@staff_required
def dashboard_messages(request):
    return render(request, 'shop/dashboard_list.html', {'section': 'Messages', 'description': 'Read customer questions and order-related communication.', 'contact_messages': ContactMessage.objects.select_related('user', 'order').order_by('-created_at')})

def logout_user(request):
    logout(request)
    return redirect('home')

def home(request):
    sale_products = Product.objects.filter(offer_type__in=['offer', 'flash_sale'], discount_percent__gt=0, stock__gt=0).filter(Q(offer_ends_at__isnull=True) | Q(offer_ends_at__gte=timezone.now())).order_by('-discount_percent', 'name')[:4]
    return render(request, 'shop/home.html', {'featured': Product.objects.filter(is_featured=True)[:4], 'new_arrivals': Product.objects.order_by('-created_at')[:8], 'sale_products': sale_products})

def careers(request):
    jobs = JobPosting.objects.filter(is_published=True).filter(Q(closing_date__isnull=True) | Q(closing_date__gte=timezone.localdate()))
    return render(request, 'shop/careers.html', {'jobs': jobs})

def career_detail(request, slug):
    job = get_object_or_404(JobPosting, slug=slug, is_published=True)
    closed = bool(job.closing_date and job.closing_date < timezone.localdate())
    form = JobApplicationForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and not closed and form.is_valid():
        application = form.save(commit=False)
        application.job = job
        application.save()
        send_mail(f'New job application: {job.title}', f'{application.full_name} applied for {job.title}. Email: {application.email}.', settings.DEFAULT_FROM_EMAIL, [settings.SUPPORT_EMAIL], fail_silently=True)
        messages.success(request, 'Your application has been received. Thank you for your interest in phoneCase254.')
        return redirect('career_detail', slug=job.slug)
    return render(request, 'shop/career_detail.html', {'job': job, 'form': form, 'closed': closed})

def shop(request):
    products = Product.objects.all().select_related('category')
    category = request.GET.get('category')
    query = request.GET.get('q', '').strip()
    if category: products = products.filter(category__slug=category)
    if query: products = products.filter(name__icontains=query)
    sale_products = Product.objects.filter(offer_type__in=['offer', 'flash_sale'], discount_percent__gt=0, stock__gt=0).filter(Q(offer_ends_at__isnull=True) | Q(offer_ends_at__gte=timezone.now())).order_by('-discount_percent', 'name')[:4]
    return render(request, 'shop/shop.html', {'products': products, 'active_category': category, 'query': query, 'sale_products': sale_products})

def offers(request):
    products = Product.objects.filter(offer_type__in=['offer', 'flash_sale'], discount_percent__gt=0, stock__gt=0).filter(Q(offer_ends_at__isnull=True) | Q(offer_ends_at__gte=timezone.now())).select_related('category').order_by('-offer_type', '-discount_percent', 'name')
    return render(request, 'shop/offers.html', {'products': products})

def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug)
    related = Product.objects.filter(category=product.category).exclude(pk=product.pk)[:3]
    can_review = False
    if request.user.is_authenticated:
        can_review = OrderItem.objects.filter(product=product, order__user=request.user).filter(Q(order__payment_status='paid') | Q(order__status='delivered')).exists() and not ProductReview.objects.filter(product=product, user=request.user).exists()
    return render(request, 'shop/product_detail.html', {'product': product, 'related': related, 'reviews': product.reviews.select_related('user').all(), 'can_review': can_review})

def _cart_items(request):
    cart = request.session.get('cart', {})
    products = Product.objects.filter(pk__in=cart.keys())
    items, total = [], Decimal('0')
    unavailable = []
    for product in products:
        if product.stock < 1:
            unavailable.append(product.name)
            continue
        quantity = min(int(cart.get(str(product.pk), 1)), product.stock)
        line_total = product.sale_price * quantity
        items.append({'product': product, 'quantity': quantity, 'line_total': line_total})
        total += line_total
    if unavailable:
        request.session['cart'] = {key: value for key, value in cart.items() if key not in {str(product.pk) for product in products if product.stock < 1}}
        request.session.modified = True
        messages.error(request, f"{', '.join(unavailable)} is out of stock and was removed from your bag.")
    return items, total

def _cart_totals(subtotal):
    delivery_fee = (subtotal * DELIVERY_RATE).quantize(Decimal('0.01'))
    if subtotal > FREE_DELIVERY_DISCOUNT_THRESHOLD:
        delivery_fee = (delivery_fee * Decimal('0.50')).quantize(Decimal('0.01'))
    return delivery_fee, subtotal + delivery_fee

def _order_totals(subtotal, payment_method='prepaid', points_available=0, redeem_points=False):
    gross_delivery = (subtotal * DELIVERY_RATE).quantize(Decimal('0.01'))
    if subtotal > FREE_DELIVERY_DISCOUNT_THRESHOLD:
        item_discount = (subtotal * PREPAID_ITEM_DISCOUNT_RATE).quantize(Decimal('0.01')) if payment_method == 'prepaid' else Decimal('0')
        delivery_discount = (gross_delivery * Decimal('0.50')).quantize(Decimal('0.01'))
    elif payment_method == 'prepaid':
        item_discount = (subtotal * PREPAID_ITEM_DISCOUNT_RATE).quantize(Decimal('0.01'))
        delivery_discount = (gross_delivery * PREPAID_DELIVERY_DISCOUNT_RATE).quantize(Decimal('0.01'))
    else:
        item_discount = Decimal('0')
        delivery_discount = Decimal('0')
    delivery_fee = gross_delivery - delivery_discount
    points_discount = min(Decimal(points_available), subtotal - item_discount + delivery_fee) if redeem_points else Decimal('0')
    points_discount = points_discount.quantize(Decimal('0.01'))
    total = subtotal - item_discount + delivery_fee - points_discount
    return item_discount, delivery_discount, delivery_fee, points_discount, total

def _send_order_invoice(order):
    items = [
        {'product': item.product, 'quantity': item.quantity, 'line_total': item.line_total}
        for item in order.items.select_related('product').all()
    ]
    order_lines = '\n'.join(f'- {item["product"].name} x {item["quantity"]}: KSh {item["line_total"]}' for item in items)
    invoice_context = {'order': order, 'items': items, 'customer_email': order.user.email}
    html_invoice = render_to_string('shop/emails/order_invoice.html', invoice_context)
    text_invoice = f'phoneCase254 order invoice {order.public_reference}\n\nCustomer: {order.full_name}\nEmail: {order.user.email}\nPhone: {order.phone}\nDelivery address: {order.delivery_address}\n\n{order_lines}\n\nSubtotal: KSh {order.subtotal}\nItem discount: KSh {order.item_discount}\nDelivery discount: KSh {order.delivery_discount}\nPoints discount: KSh {order.points_discount}\nDelivery fee: KSh {order.delivery_fee}\nTotal: KSh {order.total}\n'
    recipients = list(dict.fromkeys(email for email in [settings.ORDER_NOTIFICATION_EMAIL, order.user.email] if email))
    invoice_email = EmailMultiAlternatives(f'phoneCase254 invoice — {order.public_reference}', text_invoice, settings.DEFAULT_FROM_EMAIL, recipients, reply_to=[order.user.email] if order.user.email else None)
    invoice_email.attach_alternative(html_invoice, 'text/html')
    try:
        invoice_email.attach(f'phoneCase254-{order.public_reference}.pdf', build_invoice_pdf(order, items, order.user.email), 'application/pdf')
    except ImportError:
        logger.exception('ReportLab is not installed; sending invoice email without PDF attachment')
    invoice_email.send(fail_silently=False)

def _send_payment_failure_notice(order, reason):
    subject = f'[PAYMENT UNSUCCESSFUL] {order.public_reference} was not placed'
    text_notice = (
        f'Payment unsuccessful for phoneCase254 order {order.public_reference}.\n\n'
        f'No order was placed or confirmed.\n'
        f'Customer: {order.full_name}\n'
        f'Reason: {reason}\n\n'
        f'Please return to checkout and try again or choose pay on delivery.'
    )
    html_notice = render_to_string('shop/emails/payment_failed.html', {'order': order, 'reason': reason})
    recipients = list(dict.fromkeys(email for email in [order.user.email, settings.ORDER_NOTIFICATION_EMAIL] if email))
    notice = EmailMultiAlternatives(
        subject,
        text_notice,
        settings.DEFAULT_FROM_EMAIL,
        recipients,
        reply_to=[order.user.email] if order.user.email else None,
        headers={'X-Priority': '1', 'Importance': 'high', 'X-MSMail-Priority': 'High'},
    )
    notice.attach_alternative(html_notice, 'text/html')
    notice.send(fail_silently=False)

def cart(request):
    items, subtotal = _cart_items(request)
    delivery_fee, total = _cart_totals(subtotal)
    return render(request, 'shop/cart.html', {'items': items, 'subtotal': subtotal, 'delivery_fee': delivery_fee, 'total': total})

def add_to_cart(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    if product.stock < 1:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'ok': False, 'message': f'{product.name} is currently out of stock.'}, status=409)
        messages.error(request, f'{product.name} is currently out of stock.')
        return redirect(request.POST.get('next') or request.META.get('HTTP_REFERER') or 'shop')
    cart_data = request.session.setdefault('cart', {})
    key = str(product_id)
    if int(cart_data.get(key, 0)) >= product.stock:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'ok': False, 'message': f'Only {product.stock} unit(s) of {product.name} are available.'}, status=409)
        messages.warning(request, f'Only {product.stock} unit(s) of {product.name} are available.')
        return redirect(request.POST.get('next') or request.META.get('HTTP_REFERER') or 'shop')
    cart_data[key] = min(int(cart_data.get(key, 0)) + 1, product.stock)
    request.session.modified = True
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'ok': True, 'message': f'{product.name} added to your bag.', 'cart_count': sum(cart_data.values())})
    messages.success(request, f'{product.name} added to your bag.')
    return redirect(request.POST.get('next') or request.META.get('HTTP_REFERER') or 'shop')

def remove_from_cart(request, product_id):
    cart_data = request.session.get('cart', {})
    cart_data.pop(str(product_id), None)
    request.session['cart'] = cart_data
    return redirect('cart')

def update_cart(request):
    cart_data = request.session.get('cart', {})
    for key, value in request.POST.items():
        if key.startswith('quantity_'):
            product_id = key.split('_', 1)[1]
            product = Product.objects.filter(pk=product_id).first()
            if product: cart_data[product_id] = max(0, min(int(value or 0), product.stock))
    request.session['cart'] = {key: value for key, value in cart_data.items() if value > 0}
    return redirect('cart')

@login_required
def wishlist(request):
    return render(request, 'shop/wishlist.html', {'items': Wishlist.objects.filter(user=request.user).select_related('product')})

@login_required
def toggle_wishlist(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    item, created = Wishlist.objects.get_or_create(user=request.user, product=product)
    if not created: item.delete()
    return redirect(request.POST.get('next') or request.META.get('HTTP_REFERER') or 'shop')

@login_required
def review_product(request, slug):
    product = get_object_or_404(Product, slug=slug)
    purchase = OrderItem.objects.filter(product=product, order__user=request.user).filter(Q(order__payment_status='paid') | Q(order__status='delivered')).select_related('order').first()
    if not purchase:
        messages.error(request, 'Reviews are available after you receive or pay for a product.')
        return redirect('product_detail', product.slug)
    if ProductReview.objects.filter(product=product, user=request.user).exists():
        messages.info(request, 'You have already reviewed this product.')
        return redirect('product_detail', product.slug)
    form = ProductReviewForm(request.POST or None, request.FILES or None)
    if form.is_valid():
        with transaction.atomic():
            profile = CustomerProfile.objects.select_for_update().get(user=request.user)
            review = form.save(commit=False)
            review.user = request.user; review.product = product; review.order = purchase.order; review.points_awarded = REVIEW_POINTS; review.save()
            profile.loyalty_points += review.points_awarded
            profile.save(update_fields=['loyalty_points'])
        messages.success(request, f'Thank you for your review. {REVIEW_POINTS} loyalty points were added to your account.')
        return redirect('product_detail', product.slug)
    return render(request, 'shop/review_form.html', {'product': product, 'form': form})

def signup(request):
    if request.user.is_authenticated: return redirect('home')
    form = SignUpForm(request.POST or None)
    if form.is_valid():
        existing_user = User.objects.filter(email__iexact=form.cleaned_data['email']).first()
        if existing_user and not existing_user.is_active:
            user = existing_user
            user.username = form.cleaned_data['username']
            user.first_name = form.cleaned_data['first_name']
            user.last_name = form.cleaned_data['last_name']
            user.is_active = not settings.REQUIRE_EMAIL_CONFIRMATION
            user.set_password(form.cleaned_data['password1'])
            user.save(update_fields=['username', 'first_name', 'last_name', 'password', 'is_active'])
            CustomerProfile.objects.get_or_create(user=user)
            created_user = False
        else:
            user = form.save(commit=False); user.is_active = not settings.REQUIRE_EMAIL_CONFIRMATION; user.save(); CustomerProfile.objects.create(user=user, loyalty_points=WELCOME_POINTS)
            created_user = True
        if settings.REQUIRE_EMAIL_CONFIRMATION:
            token = default_token_generator.make_token(user)
            activation_url = request.build_absolute_uri(f'/activate/{urlsafe_base64_encode(force_bytes(user.pk))}/{token}/')
            try:
                send_mail('Confirm your phoneCase254 account', f'Welcome! Confirm your email here: {activation_url}', settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
            except Exception:
                logger.exception('Could not send account confirmation email to %s', user.email)
                if created_user:
                    user.delete()
                form.add_error(None, 'We could not send the confirmation email right now. Please try again shortly.')
                return render(request, 'registration/signup.html', {'form': form})
            return render(request, 'registration/check_email.html', {'email': user.email})
        login(request, user)
        messages.success(request, 'Your account is ready. Welcome to phoneCase254.')
        return redirect('home')
    return render(request, 'registration/signup.html', {'form': form})

def activate(request, uidb64, token):
    try: user = User.objects.get(pk=force_str(urlsafe_base64_decode(uidb64)))
    except (TypeError, ValueError, OverflowError, User.DoesNotExist): user = None
    if user and default_token_generator.check_token(user, token):
        user.is_active = True; user.save(update_fields=['is_active']); login(request, user)
        messages.success(request, 'Your email is confirmed. Welcome to phoneCase254.')
        return redirect('home')
    return render(request, 'registration/activation_invalid.html')

@login_required
def checkout(request):
    items, subtotal = _cart_items(request)
    if not items: return redirect('cart')
    profile, _ = CustomerProfile.objects.get_or_create(user=request.user)
    payment_method = request.POST.get('payment_method', 'prepaid')
    redeem_points = request.POST.get('redeem_points') == 'on'
    item_discount, delivery_discount, delivery_fee, points_discount, total = _order_totals(subtotal, payment_method, profile.loyalty_points, redeem_points)
    form = CheckoutForm(request.POST or None, initial={'full_name': request.user.get_full_name(), 'phone': profile.phone, 'mpesa_number': profile.phone, 'delivery_address': profile.default_address})
    form.fields['redeem_points'].help_text = f'{profile.loyalty_points} points available · 1 point = KSh 1.'
    if form.is_valid():
        with transaction.atomic():
            locked_profile = CustomerProfile.objects.select_for_update().get(pk=profile.pk)
            if redeem_points and locked_profile.loyalty_points < int(points_discount):
                messages.error(request, 'Your loyalty points changed. Please review the checkout total and try again.')
                return redirect('checkout')
            points_redeemed = int(points_discount)
            locked_products = {item['product'].pk: Product.objects.select_for_update().get(pk=item['product'].pk) for item in items}
            unavailable = [f'{item["product"].name} (only {locked_products[item["product"].pk].stock} left)' for item in items if locked_products[item['product'].pk].stock < item['quantity']]
            if unavailable:
                messages.error(request, f'Not enough stock: {", ".join(unavailable)}. Please update your bag.')
                return redirect('cart')
            for item in items:
                product = locked_products[item['product'].pk]
                product.stock -= item['quantity']
                product.save(update_fields=['stock'])
            order_data = {key: value for key, value in form.cleaned_data.items() if key != 'redeem_points'}
            order = Order.objects.create(user=request.user, payment_status='on_delivery' if payment_method == 'cod' else 'pending', status='queue', subtotal=subtotal, item_discount=item_discount, delivery_discount=delivery_discount, delivery_fee=delivery_fee, points_redeemed=points_redeemed, points_discount=points_discount, total=total, **order_data)
            for item in items: OrderItem.objects.create(order=order, product=item['product'], quantity=item['quantity'], price=item['product'].sale_price)
            if points_redeemed:
                locked_profile.loyalty_points -= points_redeemed
                locked_profile.save(update_fields=['loyalty_points'])
        profile.phone = order.phone; profile.default_address = order.delivery_address; profile.record_order(order)
        mpesa_started = False
        mpesa_error = ''
        if order.payment_method == 'prepaid':
            try:
                mpesa_response = initiate_stk_push(order)
                order.mpesa_checkout_request_id = mpesa_response.get('CheckoutRequestID', '')
                order.save(update_fields=['mpesa_checkout_request_id'])
                mpesa_started = True
            except Exception as error:
                mpesa_error = str(error)
        else:
            try:
                _send_order_invoice(order)
            except Exception:
                logger.exception('Could not send invoice email for order %s', order.id)
        request.session['cart'] = {}
        request.session['order_success'] = {'order_id': order.id, 'mpesa_started': mpesa_started, 'mpesa_error': mpesa_error}
        request.session.modified = True
        return redirect('order_success', order.id)
    return render(request, 'shop/checkout.html', {'form': form, 'items': items, 'subtotal': subtotal, 'item_discount': item_discount, 'delivery_discount': delivery_discount, 'points_discount': points_discount, 'available_points': profile.loyalty_points, 'delivery_fee': delivery_fee, 'total': total})

@login_required
def order_success(request, order_id):
    order = get_object_or_404(request.user.orders, pk=order_id)
    success_state = request.session.pop('order_success', {})
    return render(request, 'shop/order_success.html', {
        'order': order,
        'mpesa_number': settings.MPESA_PAYBILL_NUMBER,
        'mpesa_started': success_state.get('mpesa_started', bool(order.mpesa_checkout_request_id)),
        'mpesa_error': success_state.get('mpesa_error', ''),
    })

@login_required
def orders(request):
    profile, _ = CustomerProfile.objects.get_or_create(user=request.user)
    visible_orders = request.user.orders.filter(payment_status__in=['paid', 'on_delivery']).order_by('-created_at')
    return render(request, 'shop/orders.html', {'orders': visible_orders, 'profile': profile})

@login_required
def order_detail(request, order_id):
    order = get_object_or_404(request.user.orders.filter(payment_status__in=['paid', 'on_delivery']), pk=order_id)
    can_cancel = order.status == 'queue' and order.payment_status in ('pending', 'on_delivery') and not order.mpesa_checkout_request_id and timezone.now() < order.created_at + timedelta(minutes=3)
    return render(request, 'shop/order_detail.html', {'order': order, 'can_cancel': can_cancel})

@login_required
def track_order(request, order_id):
    order = get_object_or_404(
        request.user.orders.filter(payment_status__in=['paid', 'on_delivery']).prefetch_related('items__product', 'status_updates'),
        pk=order_id,
    )
    updates = list(order.status_updates.all())
    return render(request, 'shop/order_tracking.html', {'order': order, 'updates': updates})

@login_required
def invoice_download(request, order_id):
    order_query = Order.objects.select_related('user').prefetch_related('items__product__category')
    if request.user.is_staff:
        order = get_object_or_404(order_query, pk=order_id)
    else:
        order = get_object_or_404(order_query, pk=order_id, user=request.user, payment_status__in=['paid', 'on_delivery'])
    items = [{'product': item.product, 'quantity': item.quantity, 'line_total': item.line_total} for item in order.items.all()]
    pdf = build_invoice_pdf(order, items, order.user.email)
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="phoneCase254-{order.public_reference}.pdf"'
    return response

def _apply_mpesa_query_result(order_id, result_code, result_desc=''):
    newly_paid = False
    newly_failed = False
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order_id)
        newly_paid = result_code == '0' and order.payment_status != 'paid'
        newly_failed = result_code != '0' and order.payment_status == 'pending'
        order.mpesa_result_code = result_code
        if result_code == '0':
            order.status = 'queue'
            order.payment_status = 'paid'
            profile, _ = CustomerProfile.objects.get_or_create(user=order.user)
            profile.record_payment(order)
            order.status_updates.filter(status='cancelled').delete()
        elif newly_failed and order.status == 'queue':
            for item in order.items.all():
                product = Product.objects.select_for_update().get(pk=item.product_id)
                product.stock += item.quantity
                product.save(update_fields=['stock'])
            if order.points_redeemed:
                profile, _ = CustomerProfile.objects.select_for_update().get_or_create(user=order.user)
                profile.loyalty_points += order.points_redeemed
                profile.save(update_fields=['loyalty_points'])
            order.status = 'cancelled'
            order.payment_status = 'failed'
        order.save(update_fields=['mpesa_result_code', 'status', 'payment_status'])
    return order, newly_paid, newly_failed

@login_required
def order_status(request, order_id):
    order = get_object_or_404(request.user.orders, pk=order_id)
    if order.payment_method == 'prepaid' and order.payment_status in ('pending', 'failed') and order.mpesa_checkout_request_id:
        try:
            query = query_stk_push(order)
            result_code = query.get('ResultCode')
            result_desc = query.get('ResultDesc', '')
            logger.info('M-Pesa STK query for %s returned code=%s description=%s', order.public_reference, result_code, result_desc)
            if str(result_code) == '0':
                order, newly_paid, newly_failed = _apply_mpesa_query_result(order.id, '0', result_desc)
                if newly_paid:
                    try:
                        _send_order_invoice(order)
                    except Exception:
                        logger.exception('Could not send queried-payment invoice for order %s', order.id)
            elif result_code is not None:
                # Safaricom's callback is authoritative; do not cancel an order from a poll response.
                logger.info('Leaving order %s pending until callback confirms query code=%s', order.public_reference, result_code)
        except Exception:
            logger.debug('M-Pesa status query is still pending for order %s', order.id, exc_info=True)
    response = JsonResponse({'status': order.status, 'payment_status': order.payment_status, 'receipt': order.mpesa_receipt})
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response

@login_required
@require_POST
def cancel_order(request, order_id):
    with transaction.atomic():
        order = get_object_or_404(request.user.orders.select_for_update().prefetch_related('items__product'), pk=order_id)
        if order.status != 'queue' or order.payment_status not in ('pending', 'on_delivery') or order.mpesa_checkout_request_id or timezone.now() >= order.created_at + timedelta(minutes=3):
            messages.error(request, 'This order can no longer be cancelled online.')
            return redirect('order_detail', order.id)
        for item in order.items.all():
            product = Product.objects.select_for_update().get(pk=item.product_id)
            product.stock += item.quantity
            product.save(update_fields=['stock'])
        if order.points_redeemed:
            profile = CustomerProfile.objects.select_for_update().get(user=request.user)
            profile.loyalty_points += order.points_redeemed
            profile.save(update_fields=['loyalty_points'])
        order.status = 'cancelled'
        order.save(update_fields=['status'])
    subject = f'[ATTENTION REQUIRED] phoneCase254 {order.public_reference} CANCELLED'
    text_notice = (
        f'ATTENTION REQUIRED\n\n'
        f'Order {order.public_reference} was cancelled by {order.full_name}.\n'
        f'Customer email: {request.user.email}\n'
        f'The reserved stock has been returned to inventory.\n'
        f'Total: KSh {order.total}\n'
    )
    html_notice = render_to_string('shop/emails/order_cancelled.html', {'order': order, 'customer_email': request.user.email, 'cancelled_at': timezone.now()})
    owner_email_sent = False
    for recipient in dict.fromkeys(email for email in [settings.ORDER_NOTIFICATION_EMAIL, request.user.email] if email):
        if not recipient:
            continue
        try:
            notice = EmailMultiAlternatives(
                subject,
                text_notice,
                settings.DEFAULT_FROM_EMAIL,
                [recipient],
                reply_to=[request.user.email] if request.user.email else None,
                headers={'X-Priority': '1', 'Importance': 'high', 'X-MSMail-Priority': 'High'},
            )
            notice.attach_alternative(html_notice, 'text/html')
            notice.send(fail_silently=False)
            owner_email_sent = owner_email_sent or recipient == settings.ORDER_NOTIFICATION_EMAIL
        except Exception:
            logger.exception('Could not send cancellation notification for order %s to %s', order.id, recipient)
    if owner_email_sent:
        messages.success(request, f'Order #{order.id} cancelled. An attention alert was emailed to the store owner.')
    else:
        messages.warning(request, f'Order #{order.id} cancelled, but the store-owner alert could not be sent. Check the email settings.')
    return redirect('order_detail', order.id)

@login_required
def reorder(request, order_id):
    order = get_object_or_404(request.user.orders.prefetch_related('items__product'), pk=order_id)
    cart_data = request.session.get('cart', {})
    added = 0
    unavailable = []
    for item in order.items.all():
        if item.product.stock:
            key = str(item.product_id); cart_data[key] = min(int(cart_data.get(key, 0)) + item.quantity, item.product.stock); added += 1
        else:
            unavailable.append(item.product.name)
    request.session['cart'] = cart_data
    messages.success(request, f'{added} item(s) from order #{order.id} added to your bag.')
    if unavailable:
        messages.warning(request, f'Unavailable and skipped: {", ".join(unavailable)}.')
    return redirect('cart')

@login_required
def contact(request):
    form = ContactForm(request.POST or None)
    form.fields['order'].queryset = request.user.orders.order_by('-created_at')
    if form.is_valid():
        message = form.save(commit=False); message.user = request.user; message.save()
        order_reference = f'Order #{message.order_id}' if message.order_id else 'No order attached'
        notification = f'New customer message from {request.user.get_full_name() or request.user.username}.\nEmail: {request.user.email}\n{order_reference}\n\n{message.message}'
        try:
            send_mail(f'New phoneCase254 customer message from {request.user.email}', notification, settings.DEFAULT_FROM_EMAIL, [settings.ORDER_NOTIFICATION_EMAIL], fail_silently=False, reply_to=[request.user.email])
        except Exception:
            logger.exception('Could not send customer message notification for message %s', message.id)
        messages.success(request, 'Your message has been sent. We will get back to you shortly.')
        return redirect('home')
    return render(request, 'shop/contact.html', {'form': form})

@csrf_exempt
def mpesa_callback(request):
    if request.method != 'POST': return HttpResponse(status=405)
    try:
        callback = json.loads(request.body).get('Body', {}).get('stkCallback', {})
        checkout_request_id = callback.get('CheckoutRequestID', '')
        order = Order.objects.filter(mpesa_checkout_request_id=checkout_request_id).first()
        if order:
            result_code = str(callback.get('ResultCode', ''))
            newly_paid = result_code == '0' and order.payment_status != 'paid'
            newly_failed = result_code != '0' and order.payment_status == 'pending'
            with transaction.atomic():
                order = Order.objects.select_for_update().get(pk=order.pk)
                order.mpesa_result_code = result_code
                if result_code == '0':
                    metadata = {item.get('Name'): item.get('Value') for item in callback.get('CallbackMetadata', {}).get('Item', [])}
                    order.mpesa_receipt = str(metadata.get('MpesaReceiptNumber', ''))
                    order.status = 'queue'
                    order.payment_status = 'paid'
                    profile, _ = CustomerProfile.objects.get_or_create(user=order.user)
                    profile.record_payment(order)
                    order.status_updates.filter(status='cancelled').delete()
                else:
                    if newly_failed and order.status == 'queue':
                        for item in order.items.all():
                            product = Product.objects.select_for_update().get(pk=item.product_id)
                            product.stock += item.quantity
                            product.save(update_fields=['stock'])
                        if order.points_redeemed:
                            profile, _ = CustomerProfile.objects.select_for_update().get_or_create(user=order.user)
                            profile.loyalty_points += order.points_redeemed
                            profile.save(update_fields=['loyalty_points'])
                        order.status = 'cancelled'
                    order.payment_status = 'failed'
                order.save(update_fields=['mpesa_result_code', 'mpesa_receipt', 'status', 'payment_status'])
            if newly_paid:
                try:
                    _send_order_invoice(order)
                except Exception:
                    logger.exception('Could not send confirmed-payment invoice for order %s', order.id)
            elif newly_failed:
                reason = callback.get('ResultDesc') or 'The M-Pesa payment was declined or cancelled.'
                try:
                    _send_payment_failure_notice(order, reason)
                except Exception:
                    logger.exception('Could not send payment failure notice for order %s', order.id)
    except (ValueError, TypeError, AttributeError):
        pass
    return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Callback processed'})



def faq(request):
    return render(request, 'shop/faq.html')

@require_POST
def nova_ai(request):
    provider_url = os.environ.get('NOVA_AI_URL', 'https://api.openai.com/v1/chat/completions')
    api_key = os.environ.get('NOVA_AI_API_KEY', '')
    model = os.environ.get('NOVA_AI_MODEL', 'gpt-4o-mini')
    if not api_key:
        return JsonResponse({'ok': False, 'message': 'Nova AI is currently in quick-answer mode. Please try a FAQ topic or contact support.'}, status=503)
    try:
        payload = json.loads(request.body or '{}')
        question = str(payload.get('message', '')).strip()[:2000]
        history = payload.get('history', [])[-8:]
        if not question:
            return JsonResponse({'ok': False, 'message': 'Please type a question.'}, status=400)
        messages = [{'role': 'system', 'content': 'You are Nova AI, the friendly phoneCase254 customer support assistant. Give accurate, concise help about phone cases, products, offers, orders, delivery, M-Pesa, tracking, returns, rewards, careers, and account support. Use an empathetic tone when a customer sounds worried or frustrated, but do not claim to know their feelings or make medical or financial diagnoses. Ask one clarifying question when needed. Never invent order details, payment results, stock, company policies, CEO facts, or personal data. Direct customers to /shop/, /offers/, /orders/, /careers/, /faq/, or support when appropriate. The Founder and CEO is Vincent Kiprotich; LinkedIn: www.linkedin.com/in/vincent-kiprotich-84257b221.'}]
        for item in history:
            if isinstance(item, dict) and item.get('role') in ('user', 'assistant'):
                messages.append({'role': item['role'], 'content': str(item.get('content', ''))[:2000]})
        messages.append({'role': 'user', 'content': question})
        response = requests.post(provider_url, headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}, json={'model': model, 'messages': messages, 'temperature': 0.4, 'max_tokens': 350}, timeout=20)
        response.raise_for_status()
        data = response.json()
        answer = data['choices'][0]['message']['content'].strip()
        return JsonResponse({'ok': True, 'message': answer})
    except (requests.RequestException, KeyError, ValueError, TypeError) as error:
        logger.warning('Nova AI request failed: %s', error)
        return JsonResponse({'ok': False, 'message': 'Nova AI is temporarily unavailable. I can still help with the FAQ topics or connect you to support.'}, status=502)











