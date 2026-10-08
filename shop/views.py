from decimal import Decimal
import json
from datetime import timedelta
from django.conf import settings
import logging

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives, send_mail
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils import timezone
from django.contrib.auth.tokens import default_token_generator
from .forms import CheckoutForm, ContactForm, ProductReviewForm, SignUpForm
from .models import Category, CustomerProfile, Order, OrderItem, Product, ProductReview, Wishlist
from .services.mpesa import initiate_stk_push
from .services.invoice import build_invoice_pdf

logger = logging.getLogger(__name__)
DELIVERY_RATE = Decimal('0.10')
PREPAID_ITEM_DISCOUNT_RATE = Decimal('0.05')
PREPAID_DELIVERY_DISCOUNT_RATE = Decimal('0.06')
WELCOME_POINTS = 50
REVIEW_POINTS = 25
FREE_DELIVERY_DISCOUNT_THRESHOLD = Decimal('2000')

def logout_user(request):
    logout(request)
    return redirect('home')

def home(request):
    return render(request, 'shop/home.html', {'featured': Product.objects.filter(is_featured=True)[:4], 'new_arrivals': Product.objects.order_by('-created_at')[:8]})

def shop(request):
    products = Product.objects.all().select_related('category')
    category = request.GET.get('category')
    query = request.GET.get('q', '').strip()
    if category: products = products.filter(category__slug=category)
    if query: products = products.filter(name__icontains=query)
    return render(request, 'shop/shop.html', {'products': products, 'active_category': category, 'query': query})

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
        line_total = product.price * quantity
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
            order = Order.objects.create(user=request.user, subtotal=subtotal, item_discount=item_discount, delivery_discount=delivery_discount, delivery_fee=delivery_fee, points_redeemed=points_redeemed, points_discount=points_discount, total=total, **order_data)
            for item in items: OrderItem.objects.create(order=order, product=item['product'], quantity=item['quantity'], price=item['product'].price)
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
    return render(request, 'shop/orders.html', {'orders': request.user.orders.order_by('-created_at'), 'profile': profile})

@login_required
def order_detail(request, order_id):
    order = get_object_or_404(request.user.orders, pk=order_id)
    can_cancel = order.status == 'pending' and order.payment_status == 'pending' and not order.mpesa_checkout_request_id and timezone.now() < order.created_at + timedelta(minutes=3)
    return render(request, 'shop/order_detail.html', {'order': order, 'can_cancel': can_cancel})

@login_required
def order_status(request, order_id):
    order = get_object_or_404(request.user.orders, pk=order_id)
    response = JsonResponse({'status': order.status, 'payment_status': order.payment_status, 'receipt': order.mpesa_receipt})
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response

@login_required
@require_POST
def cancel_order(request, order_id):
    with transaction.atomic():
        order = get_object_or_404(request.user.orders.select_for_update().prefetch_related('items__product'), pk=order_id)
        if order.status != 'pending' or order.payment_status != 'pending' or order.mpesa_checkout_request_id or timezone.now() >= order.created_at + timedelta(minutes=3):
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
                    order.status = 'confirmed'
                    order.payment_status = 'paid'
                    profile, _ = CustomerProfile.objects.get_or_create(user=order.user)
                    profile.record_payment(order)
                else:
                    if newly_failed and order.status == 'pending':
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
