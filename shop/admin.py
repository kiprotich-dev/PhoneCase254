from django.contrib import admin
from .models import Category, ContactMessage, CustomerProfile, Order, OrderItem, Product, ProductReview, Wishlist

admin.site.site_header = 'phoneCase254 studio'
admin.site.site_title = 'phoneCase254 Admin'
admin.site.index_title = 'Store overview'

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'stock', 'is_featured')
    list_filter = ('category', 'is_featured')
    prepopulated_fields = {'slug': ('name',)}
    fieldsets = ((None, {'fields': ('name', 'slug', 'category', 'description', 'price', 'stock')}), ('Product media', {'fields': ('image_url', 'image', 'accent')}), ('Merchandising', {'fields': ('is_featured',)}))

admin.site.register(Category)
admin.site.register(Wishlist)
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('public_reference', 'customer_name', 'user_email', 'total', 'payment_method', 'payment_status', 'status', 'created_at')
    list_filter = ('payment_method', 'payment_status', 'status', 'created_at')
    search_fields = ('public_reference', 'full_name', 'phone', 'mpesa_number', 'user__username', 'user__email')
    readonly_fields = ('created_at', 'mpesa_checkout_request_id', 'mpesa_receipt', 'mpesa_result_code')
    def customer_name(self, obj): return obj.full_name
    def user_email(self, obj): return obj.user.email
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.payment_status == 'paid' and not obj.loyalty_awarded:
            profile, _ = CustomerProfile.objects.get_or_create(user=obj.user)
            profile.record_payment(obj)
    customer_name.short_description = 'Customer'
    user_email.short_description = 'Email'

admin.site.register(CustomerProfile)
admin.site.register(ContactMessage)
admin.site.register(OrderItem)

@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'rating', 'points_awarded', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('product__name', 'user__username', 'user__email', 'title', 'body')
    readonly_fields = ('user', 'product', 'order', 'points_awarded', 'created_at', 'updated_at')
