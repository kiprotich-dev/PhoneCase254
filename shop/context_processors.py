from .models import Category, Wishlist

def store_context(request):
    cart = request.session.get('cart', {})
    cart_count = sum(cart.values())
    wishlist_count = Wishlist.objects.filter(user=request.user).count() if request.user.is_authenticated else 0
    return {'nav_categories': Category.objects.all(), 'cart_count': cart_count, 'wishlist_count': wishlist_count}

