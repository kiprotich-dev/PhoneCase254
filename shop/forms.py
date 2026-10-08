from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import ContactMessage, Order, ProductReview

class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True, help_text='We will send a confirmation link here.')
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'username', 'password1', 'password2')
    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        existing = User.objects.filter(email__iexact=email).first()
        if existing and existing.is_active:
            raise forms.ValidationError('An account with this email already exists. Please log in or reset your password.')
        return email

class CheckoutForm(forms.Form):
    full_name = forms.CharField(max_length=160)
    phone = forms.CharField(max_length=30, label='Phone number')
    mpesa_number = forms.CharField(max_length=30, label='M-Pesa number', help_text='The number that will receive the payment prompt.')
    delivery_address = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), label='Delivery address')
    payment_method = forms.ChoiceField(choices=Order.PAYMENT_METHODS, widget=forms.RadioSelect, initial='prepaid', label='Payment option')
    customer_note = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}), label='Delivery note')
    redeem_points = forms.BooleanField(required=False, label='Use my loyalty points')

class ContactForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ('order', 'message')
        widgets = {'order': forms.Select(attrs={'class': 'select-control'}), 'message': forms.Textarea(attrs={'rows': 5, 'placeholder': 'How can we help?'})}

class ProductReviewForm(forms.ModelForm):
    class Meta:
        model = ProductReview
        fields = ('rating', 'title', 'body', 'image')
        widgets = {'body': forms.Textarea(attrs={'rows': 5, 'placeholder': 'What did you like about this case?'})}
