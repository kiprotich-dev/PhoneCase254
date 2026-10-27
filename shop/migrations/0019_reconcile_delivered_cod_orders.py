from django.db import migrations

def reconcile_delivered_cash_orders(apps, schema_editor):
    Order = apps.get_model('shop', 'Order')
    CustomerProfile = apps.get_model('shop', 'CustomerProfile')
    delivered_orders = Order.objects.filter(payment_method='cod', status='delivered', payment_status='on_delivery').prefetch_related('items')
    for order in delivered_orders:
        order.payment_status = 'paid'
        update_fields = ['payment_status']
        if not order.loyalty_awarded:
            profile, _ = CustomerProfile.objects.get_or_create(user_id=order.user_id)
            earned_points = sum(item.quantity * 5 for item in order.items.all() if item.price > 500)
            profile.completed_orders += 1
            profile.lifetime_spend += order.total
            profile.loyalty_points += earned_points
            if profile.lifetime_spend >= 50000:
                profile.tier = 'gold'
            elif profile.lifetime_spend >= 20000:
                profile.tier = 'silver'
            profile.save(update_fields=['completed_orders', 'lifetime_spend', 'loyalty_points', 'tier'])
            order.loyalty_awarded = True
            update_fields.append('loyalty_awarded')
        order.save(update_fields=update_fields)

def reverse_reconcile(apps, schema_editor):
    # Payment recognition is intentionally not reversed; it reflects money received.
    pass


class Migration(migrations.Migration):
    dependencies = [('shop', '0018_jobposting_jobapplication')]
    operations = [migrations.RunPython(reconcile_delivered_cash_orders, reverse_reconcile)]

