from django.contrib.auth import views as auth_views
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'), path('shop/', views.shop, name='shop'), path('shop/<slug:slug>/', views.product_detail, name='product_detail'), path('shop/<slug:slug>/review/', views.review_product, name='review_product'),
    path('cart/', views.cart, name='cart'), path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'), path('cart/remove/<int:product_id>/', views.remove_from_cart, name='remove_from_cart'), path('cart/update/', views.update_cart, name='update_cart'),
    path('wishlist/', views.wishlist, name='wishlist'), path('wishlist/toggle/<int:product_id>/', views.toggle_wishlist, name='toggle_wishlist'),
    path('signup/', views.signup, name='signup'), path('activate/<uidb64>/<token>/', views.activate, name='activate'),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'), path('logout/', views.logout_user, name='logout'),
    path('password-reset/', auth_views.PasswordResetView.as_view(template_name='registration/password_reset_form.html', email_template_name='registration/password_reset_email.txt', subject_template_name='registration/password_reset_subject.txt'), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='registration/password_reset_confirm.html'), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'), name='password_reset_complete'),
    path('checkout/', views.checkout, name='checkout'), path('order-success/<int:order_id>/', views.order_success, name='order_success'), path('orders/', views.orders, name='orders'), path('orders/<int:order_id>/', views.order_detail, name='order_detail'), path('orders/<int:order_id>/status/', views.order_status, name='order_status'), path('orders/<int:order_id>/cancel/', views.cancel_order, name='cancel_order'), path('orders/<int:order_id>/reorder/', views.reorder, name='reorder'),
    path('contact/', views.contact, name='contact'),
    path('mpesa/callback/', views.mpesa_callback, name='mpesa_callback'),
]
