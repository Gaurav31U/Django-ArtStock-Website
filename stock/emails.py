"""Transactional emails. In development they print to the console (see EMAIL_BACKEND)."""
import logging

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

log = logging.getLogger(__name__)


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
	"""Token stops working once the email is verified or changed."""
	key_salt = 'stock.emails.EmailVerificationTokenGenerator'

	def _make_hash_value(self, user, timestamp):
		return f'{user.pk}{user.email}{user.email_verified}{timestamp}'


email_verification_token = EmailVerificationTokenGenerator()


def _send(subject, template, context, to):
	recipients = [e for e in to if e]
	if not recipients:
		return
	context = {'site_url': settings.SITE_URL, **context}
	body = render_to_string(f'emails/{template}.txt', context)
	try:
		send_mail(f'ArtStock · {subject}', body, settings.DEFAULT_FROM_EMAIL, recipients)
	except Exception:  # never break a checkout because the mail server is down
		log.exception('Failed to send "%s" email to %s', subject, recipients)


def order_placed(customer, orders):
	total = sum(o.total_amount for o in orders)
	_send('Order confirmed', 'order_placed', {'customer': customer, 'orders': orders, 'total': total},
	      [customer.email or customer.user.email])
	by_artist = {}
	for o in orders:
		by_artist.setdefault(o.Art_id.Artist_id, []).append(o)
	for artist, items in by_artist.items():
		_send('You have a new order', 'artist_new_order', {'artist': artist, 'orders': items, 'customer': customer},
		      [artist.email or artist.user.email])


def order_status_changed(order):
	customer = order.orderedBy
	_send(f'Order #{order.O_id} is {order.status.lower()}', 'order_status', {'order': order, 'customer': customer},
	      [customer.email or customer.user.email])


def verification_link(user):
	uid = urlsafe_base64_encode(force_bytes(user.pk))
	token = email_verification_token.make_token(user)
	return settings.SITE_URL + reverse('verify_email', args=[uid, token])


def verify_email(user):
	_send('Confirm your email', 'verify_email', {'user': user, 'link': verification_link(user)}, [user.email])
