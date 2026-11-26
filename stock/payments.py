"""Minimal Razorpay client (no SDK needed).

Online payment is switched on only when RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET are set.
Use test-mode keys (rzp_test_...) from the Razorpay dashboard while developing.
"""
import base64
import hashlib
import hmac
import json
import urllib.error
import urllib.request

from django.conf import settings

API_URL = 'https://api.razorpay.com/v1/orders'


class PaymentError(Exception):
	pass


def is_enabled():
	return bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)


def create_order(amount_rupees, receipt):
	"""Create a Razorpay order and return its id. Amounts are sent in paise."""
	payload = json.dumps({'amount': int(amount_rupees) * 100, 'currency': 'INR', 'receipt': receipt}).encode()
	token = base64.b64encode(f'{settings.RAZORPAY_KEY_ID}:{settings.RAZORPAY_KEY_SECRET}'.encode()).decode()
	req = urllib.request.Request(API_URL, data=payload, method='POST', headers={
		'Content-Type': 'application/json',
		'Authorization': f'Basic {token}',
	})
	try:
		with urllib.request.urlopen(req, timeout=15) as resp:
			return json.loads(resp.read())['id']
	except (urllib.error.URLError, KeyError, ValueError) as exc:
		raise PaymentError(f'Could not start the payment: {exc}') from exc


def verify_signature(gateway_order_id, payment_id, signature):
	"""Check the signature Razorpay Checkout returns after a successful payment."""
	if not (gateway_order_id and payment_id and signature):
		return False
	expected = hmac.new(settings.RAZORPAY_KEY_SECRET.encode(), f'{gateway_order_id}|{payment_id}'.encode(),
	                    hashlib.sha256).hexdigest()
	return hmac.compare_digest(expected, signature)
