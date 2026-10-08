from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from django.utils import timezone

class Category(models.Model):
    name = models.CharField(max_length=80)
    slug = models.SlugField(unique=True, blank=True)
    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    def __str__(self): return self.name

class Product(models.Model):
    name = models.CharField(max_length=160)
    slug = models.SlugField(unique=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    image_url = models.URLField(blank=True, help_text='Optional hosted product photo URL from Unsplash, Pexels, or your own CDN.')
    accent = models.CharField(max_length=7, default='#e7d9ca', help_text='Fallback card colour, e.g. #e7d9ca')
    is_featured = models.BooleanField(default=False)
    stock = models.PositiveIntegerField(default=25)
    created_at = models.DateTimeField(auto_now_add=True)
    def save(self, *args, **kwargs):
        if not self.slug: self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    def get_absolute_url(self): return reverse('product_detail', args=[self.slug])
    def __str__(self): return self.name

class Wishlist(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wishlist')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    class Meta: constraints = [models.UniqueConstraint(fields=['user', 'product'], name='one_wishlist_item')]

class ProductReview(models.Model):
    RATING_CHOICES = [(value, f'{value} star' if value == 1 else f'{value} stars') for value in range(1, 6)]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='product_reviews')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    order = models.ForeignKey('Order', on_delete=models.SET_NULL, null=True, blank=True, related_name='reviews')
    rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES)
    title = models.CharField(max_length=120)
    body = models.TextField()
    image = models.ImageField(upload_to='reviews/', blank=True, null=True)
    points_awarded = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['user', 'product'], name='one_review_per_customer_product')]
    def __str__(self): return f'{self.product.name} review by {self.user.username}'

class CustomerProfile(models.Model):
    TIER_CHOICES = [('standard', 'Standard'), ('silver', 'Silver'), ('gold', 'Gold')]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='customer_profile')
    phone = models.CharField(max_length=30, blank=True)
    default_address = models.TextField(blank=True)
    loyalty_points = models.PositiveIntegerField(default=50)
    total_orders = models.PositiveIntegerField(default=0)
    completed_orders = models.PositiveIntegerField(default=0)
    lifetime_spend = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tier = models.CharField(max_length=20, choices=TIER_CHOICES, default='standard')
    last_order_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return f'{self.user.get_full_name() or self.user.username} — {self.tier.title()}'
    def record_order(self, order, completed=False):
        self.total_orders += 1; self.last_order_at = timezone.now()
        if completed:
            self.completed_orders += 1; self.lifetime_spend += order.total; self.loyalty_points += int(order.total // 100)
        if self.lifetime_spend >= 50000: self.tier = 'gold'
        elif self.lifetime_spend >= 20000: self.tier = 'silver'
        self.save()
    def record_payment(self, order):
        if order.loyalty_awarded: return
        earned_points = sum(item.quantity * 5 for item in order.items.all() if item.price > 500)
        self.completed_orders += 1; self.lifetime_spend += order.total; self.loyalty_points += earned_points
        if self.lifetime_spend >= 50000: self.tier = 'gold'
        elif self.lifetime_spend >= 20000: self.tier = 'silver'
        self.save()
        order.loyalty_awarded = True
        order.save(update_fields=['loyalty_awarded'])

class Order(models.Model):
    STATUS_CHOICES = [('pending', 'Pending payment'), ('confirmed', 'Confirmed'), ('packed', 'Packed'), ('shipped', 'Shipped'), ('delivered', 'Delivered'), ('cancelled', 'Cancelled')]
    PAYMENT_METHODS = [('prepaid', 'Pay before delivery'), ('cod', 'Pay on delivery')]
    PAYMENT_STATUSES = [('pending', 'Pending payment'), ('paid', 'Paid'), ('failed', 'Failed')]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='orders')
    public_reference = models.CharField(max_length=32, unique=True, blank=True)
    full_name = models.CharField(max_length=160)
    phone = models.CharField(max_length=30)
    delivery_address = models.TextField()
    customer_note = models.TextField(blank=True)
    mpesa_number = models.CharField(max_length=30)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='prepaid')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUSES, default='pending')
    loyalty_awarded = models.BooleanField(default=False)
    mpesa_checkout_request_id = models.CharField(max_length=100, blank=True)
    mpesa_receipt = models.CharField(max_length=100, blank=True)
    mpesa_result_code = models.CharField(max_length=20, blank=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    item_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    points_redeemed = models.PositiveIntegerField(default=0)
    points_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new and not self.public_reference:
            self.public_reference = f'PC254-{self.created_at:%Y%m%d}-{self.pk:04d}'
            super().save(update_fields=['public_reference'])
    def __str__(self): return f'{self.public_reference or self.pk} - {self.full_name}'

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    @property
    def line_total(self): return self.quantity * self.price

class ContactMessage(models.Model):
    STATUS_CHOICES = [('new', 'New'), ('read', 'Read'), ('replied', 'Replied')]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='contact_messages')
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True, related_name='messages')
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return f'{self.user.username} · {self.created_at:%d %b %Y %H:%M}'
