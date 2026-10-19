from django.contrib.auth import views as auth_views
from django.urls import path
from . import views

urlpatterns = [
    path('store-control-254/', views.dashboard, name='dashboard'),
    path('store-control-254/products/', views.dashboard_products, name='dashboard_products'),
    path('store-control-254/products/new/', views.dashboard_product_add, name='dashboard_product_add'),
    path('store-control-254/products/<int:product_id>/offer/', views.dashboard_offer_update, name='dashboard_offer_update'),
    path('store-control-254/orders/', views.dashboard_orders, name='dashboard_orders'),
    path('store-control-254/orders/<int:order_id>/status/', views.dashboard_order_status_update, name='dashboard_order_status_update'),
    path('store-control-254/customers/', views.dashboard_customers, name='dashboard_customers'),
    path('store-control-254/inventory/', views.dashboard_inventory, name='dashboard_inventory'),
    path('store-control-254/inventory/<int:product_id>/stock/', views.dashboard_stock_update, name='dashboard_stock_update'),
    path('store-control-254/messages/', views.dashboard_messages, name='dashboard_messages'),
    path('store-control-254/reports/export/', views.dashboard_report_export, name='dashboard_report_export'),
    path('store-control-254/reports/', views.dashboard_reports, name='dashboard_reports'),
    path('store-control-254/settings/', views.dashboard_settings, name='dashboard_settings'),
    path('store-control-254/search/', views.dashboard_search, name='dashboard_search'),
    path('', views.home, name='home'), path('careers/', views.careers, name='careers'), path('careers/<slug:slug>/', views.career_detail, name='career_detail'), path('offers/', views.offers, name='offers'), path('shop/', views.shop, name='shop'), path('shop/<slug:slug>/', views.product_detail, name='product_detail'), path('shop/<slug:slug>/review/', views.review_product, name='review_product'),
    path('cart/', views.cart, name='cart'), path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'), path('cart/remove/<int:product_id>/', views.remove_from_cart, name='remove_from_cart'), path('cart/update/', views.update_cart, name='update_cart'),
    path('wishlist/', views.wishlist, name='wishlist'), path('wishlist/toggle/<int:product_id>/', views.toggle_wishlist, name='toggle_wishlist'),
    path('signup/', views.signup, name='signup'), path('activate/<uidb64>/<token>/', views.activate, name='activate'),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'), path('logout/', views.logout_user, name='logout'),
    path('password-reset/', auth_views.PasswordResetView.as_view(template_name='registration/password_reset_form.html', email_template_name='registration/password_reset_email.txt', subject_template_name='registration/password_reset_subject.txt'), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='registration/password_reset_confirm.html'), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'), name='password_reset_complete'),
    path('checkout/', views.checkout, name='checkout'), path('order-success/<int:order_id>/', views.order_success, name='order_success'), path('orders/', views.orders, name='orders'), path('orders/<int:order_id>/', views.order_detail, name='order_detail'), path('orders/<int:order_id>/track/', views.track_order, name='track_order'), path('orders/<int:order_id>/invoice/', views.invoice_download, name='invoice_download'), path('orders/<int:order_id>/status/', views.order_status, name='order_status'), path('orders/<int:order_id>/cancel/', views.cancel_order, name='cancel_order'), path('orders/<int:order_id>/reorder/', views.reorder, name='reorder'),
    path('contact/', views.contact, name='contact'),
    path('mpesa/callback/', views.mpesa_callback, name='mpesa_callback'),
]
