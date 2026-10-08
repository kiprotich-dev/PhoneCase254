import base64
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import requests
from django.conf import settings

def _base_url():
    return 'https://api.safaricom.co.ke' if settings.MPESA_ENVIRONMENT == 'production' else 'https://sandbox.safaricom.co.ke'

def _phone_number(value):
    digits = ''.join(character for character in value if character.isdigit())
    if digits.startswith('0'): return '254' + digits[1:]
    if digits.startswith('254'): return digits
    return digits

def _access_token():
    response = requests.get(f'{_base_url()}/oauth/v1/generate?grant_type=client_credentials', auth=(settings.MPESA_CONSUMER_KEY, settings.MPESA_CONSUMER_SECRET), timeout=20)
    response.raise_for_status()
    return response.json()['access_token']

def initiate_stk_push(order):
    if not settings.MPESA_CONSUMER_KEY or not settings.MPESA_CONSUMER_SECRET or not settings.MPESA_PASSKEY:
        raise RuntimeError('M-Pesa credentials are not configured in the local environment.')
    callback_url = settings.MPESA_CALLBACK_URL
    if (
        not callback_url.startswith('https://')
        or 'your-public-domain' in callback_url
        or 'safaricom.co.ke' in callback_url
        or not callback_url.rstrip('/').endswith('/mpesa/callback')
    ):
        raise RuntimeError('Set MPESA_CALLBACK_URL to your public HTTPS URL ending in /mpesa/callback/. Do not use a Safaricom API URL.')
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    password = base64.b64encode(f'{settings.MPESA_SHORT_CODE}{settings.MPESA_PASSKEY}{timestamp}'.encode()).decode()
    payload = {
        'BusinessShortCode': settings.MPESA_SHORT_CODE,
        'Password': password,
        'Timestamp': timestamp,
        'TransactionType': 'CustomerPayBillOnline',
        'Amount': int(Decimal(order.total).quantize(Decimal('1'), rounding=ROUND_HALF_UP)),
        'PartyA': _phone_number(order.mpesa_number),
        'PartyB': settings.MPESA_SHORT_CODE,
        'PhoneNumber': _phone_number(order.mpesa_number),
        'CallBackURL': callback_url,
        'AccountReference': f'PC254-{order.pk}',
        'TransactionDesc': settings.MPESA_TRANSACTION_DESCRIPTION,
    }
    response = requests.post(f'{_base_url()}/mpesa/stkpush/v1/processrequest', json=payload, headers={'Authorization': f'Bearer {_access_token()}'}, timeout=30)
    response.raise_for_status()
    data = response.json()
    if data.get('ResponseCode') not in (None, '0'): raise RuntimeError(data.get('ResponseDescription', 'M-Pesa request was rejected.'))
    return data
