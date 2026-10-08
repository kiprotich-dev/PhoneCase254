from django.core.management.base import BaseCommand
from shop.models import Category, Product

class Command(BaseCommand):
    help = 'Add starter categories and products for phoneCase254'
    def handle(self, *args, **kwargs):
        names = ['Everyday', 'Clear', 'Statement', 'Premium']
        categories = {name.lower(): Category.objects.get_or_create(name=name)[0] for name in names}
        products = [
            ('The Everyday Case', 'everyday', 'Soft-touch protection for the days that do the most.', 1499, '#d9d2c8', True, 'https://images.unsplash.com/photo-1764053430686-5435fe548fca?auto=format&fit=crop&w=1200&q=85'),
            ('Peach Fizz', 'statement', 'A little colour, a lot of personality.', 1599, '#f1b7a8', True, 'https://images.unsplash.com/photo-1775544265981-9db0ea58687f?auto=format&fit=crop&w=1200&q=85'),
            ('Barely There', 'clear', 'Crystal-clear protection that lets your phone shine.', 1299, '#dce6e3', True, 'https://images.pexels.com/photos/7360460/pexels-photo-7360460.jpeg?auto=compress&cs=tinysrgb&w=1200'),
            ('Olive Study', 'premium', 'A considered case in a grounded, matte finish.', 1899, '#b8bd9a', True, 'https://images.unsplash.com/photo-1711033312367-247626a984d1?auto=format&fit=crop&w=1200&q=85'),
            ('Blue Hour', 'statement', 'Deep blue, clean lines, everyday confidence.', 1599, '#a7b9d2', False, 'https://images.unsplash.com/photo-1764053430686-5435fe548fca?auto=format&fit=crop&w=1200&q=85'),
            ('Honeycomb', 'premium', 'A warm amber shell with a satisfying grip.', 1799, '#e5bd77', False, 'https://images.pexels.com/photos/7360460/pexels-photo-7360460.jpeg?auto=compress&cs=tinysrgb&w=1200'),
        ]
        for name, category, description, price, accent, featured, image_url in products:
            Product.objects.update_or_create(name=name, defaults={'category': categories[category], 'description': description, 'price': price, 'accent': accent, 'is_featured': featured, 'stock': 25, 'image_url': image_url})
        self.stdout.write(self.style.SUCCESS('Starter store data is ready.'))
