import hashlib
import hmac
import re
import shutil
import tempfile
from io import BytesIO, StringIO
from unittest import mock

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import Art, Artist, Customer, Order, Review, User, Wishlist

TEMP_MEDIA = tempfile.mkdtemp()


def _jpeg(size=(2400, 1600), color=(180, 90, 40)):
	buf = BytesIO()
	Image.new('RGB', size, color).save(buf, format='JPEG', quality=95)
	return SimpleUploadedFile('big.jpg', buf.getvalue(), content_type='image/jpeg')


@override_settings(MEDIA_ROOT=TEMP_MEDIA, RAZORPAY_KEY_ID='rzp_test_unit', RAZORPAY_KEY_SECRET='unit-test-secret')
class FeaturePackTests(TestCase):
	@classmethod
	def tearDownClass(cls):
		super().tearDownClass()
		shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

	def setUp(self):
		self.artist_user = User.objects.create_user('painter2', password='s3cret-pass!', is_artist=True,
		                                            email='painter@example.com')
		self.artist = Artist.objects.create(user=self.artist_user, name='Meera Artist', email='painter@example.com',
		                                    phone='1', address='Pune')
		self.art = Art.objects.create(Artist_id=self.artist, name='Monsoon', descrip='Oil', price=2000, quantity=5,
		                              category=Art.CATEGORY_NATURE, medium='Oil on canvas', image=_jpeg())
		self.buyer_user = User.objects.create_user('buyer2', password='s3cret-pass!', is_customer=True,
		                                           email='buyer@example.com')
		self.buyer = Customer.objects.create(user=self.buyer_user, name='Kabir', email='buyer@example.com',
		                                     phone='2', address='Delhi')

	def _login_buyer(self):
		self.client.login(username='buyer2', password='s3cret-pass!')

	def _add_to_cart(self, qty=1):
		self.client.post(reverse('Add_to_Cart', args=[self.art.Art_id]), {'quantity': qty})

	# ---- images
	def test_large_upload_is_resized_and_thumbnailed(self):
		with Image.open(self.art.image.path) as im:
			self.assertLessEqual(max(im.size), 1600)
		self.assertTrue(self.art.thumbnail)
		with Image.open(self.art.thumbnail.path) as im:
			self.assertLessEqual(max(im.size), 600)
		self.assertEqual(self.art.thumb_url, self.art.thumbnail.url)

	def test_optimize_images_command(self):
		Art.objects.filter(pk=self.art.pk).update(thumbnail='')
		call_command('optimize_images', stdout=StringIO())
		self.art.refresh_from_db()
		self.assertTrue(self.art.thumbnail)

	# ---- gallery filters
	def test_price_filter_and_medium_search(self):
		Art.objects.create(Artist_id=self.artist, name='Cheap Sketch', descrip='Pencil', price=300, quantity=1,
		                   image=_jpeg((200, 200)))
		r = self.client.get(reverse('index'), {'min_price': 1000})
		self.assertContains(r, 'Monsoon')
		self.assertNotContains(r, 'Cheap Sketch')
		r = self.client.get(reverse('index'), {'max_price': 500})
		self.assertContains(r, 'Cheap Sketch')
		self.assertNotContains(r, 'Monsoon')
		self.assertContains(self.client.get(reverse('index'), {'search': 'canvas'}), 'Monsoon')

	def test_pagination(self):
		for i in range(14):
			Art.objects.create(Artist_id=self.artist, name=f'Piece {i:02d}', descrip='x', price=100 + i, quantity=1,
			                   image=_jpeg((100, 100)))
		r = self.client.get(reverse('index'))
		self.assertEqual(len(r.context['arts']), 12)
		self.assertContains(r, 'Page 1 of 2')
		r = self.client.get(reverse('index'), {'page': 2})
		self.assertEqual(len(r.context['arts']), 3)

	# ---- wishlist
	def test_wishlist_toggle(self):
		self._login_buyer()
		self.client.post(reverse('toggle_wishlist', args=[self.art.Art_id]))
		self.assertTrue(Wishlist.objects.filter(customer=self.buyer, art=self.art).exists())
		self.assertContains(self.client.get(reverse('wishlist')), 'Monsoon')
		self.client.post(reverse('toggle_wishlist', args=[self.art.Art_id]))
		self.assertFalse(Wishlist.objects.exists())

	# ---- reviews
	def test_review_requires_completed_order(self):
		self._login_buyer()
		self.client.post(reverse('add_review', args=[self.art.Art_id]), {'rating': 5, 'comment': 'Lovely'})
		self.assertFalse(Review.objects.exists())
		Order.objects.create(Art_id=self.art, orderedBy=self.buyer, quantity=1, total_amount=2000,
		                     delivery_addr='x', status=Order.ORDER_STATE_COMPLETED)
		self.client.post(reverse('add_review', args=[self.art.Art_id]), {'rating': 4, 'comment': 'Lovely'})
		self.client.post(reverse('add_review', args=[self.art.Art_id]), {'rating': 5, 'comment': 'Even better'})
		review = Review.objects.get()
		self.assertEqual((review.rating, review.comment), (5, 'Even better'))
		r = self.client.get(reverse('Art', args=[self.art.Art_id]))
		self.assertContains(r, 'Even better')
		self.assertContains(r, 'Verified buyer')

	def test_ratings_do_not_inflate_sold_count(self):
		other = Customer.objects.create(user=User.objects.create_user('b3', password='x', is_customer=True),
		                                name='B3', email='b3@example.com', phone='3', address='x')
		for c in (self.buyer, other):
			Order.objects.create(Art_id=self.art, orderedBy=c, quantity=1, total_amount=2000, delivery_addr='x',
			                     status=Order.ORDER_STATE_COMPLETED)
			Review.objects.create(art=self.art, customer=c, rating=4)
		self.client.login(username='painter2', password='s3cret-pass!')
		art = self.client.get(reverse('aprofile')).context['arts'][0]
		self.assertEqual((art.sold, art.review_count, art.avg_rating), (2, 2, 4.0))

	# ---- emails
	def test_cod_order_sends_emails_and_status_email(self):
		self._login_buyer()
		self._add_to_cart(2)
		self.client.post(reverse('payment'), {'delivery_addr': 'Delhi', 'payment_method': 'cod'})
		order = Order.objects.get(orderedBy=self.buyer)
		self.assertEqual((order.payment_method, order.payment_status), ('cod', 'pending'))
		recipients = sorted(m.to[0] for m in mail.outbox)
		self.assertEqual(recipients, ['buyer@example.com', 'painter@example.com'])
		self.assertIn('Monsoon', mail.outbox[0].body)

		mail.outbox.clear()
		self.client.login(username='painter2', password='s3cret-pass!')
		self.client.post(reverse('update_order_status', args=[order.O_id]), {'status': Order.ORDER_STATE_COMPLETED})
		order.refresh_from_db()
		self.assertEqual(order.payment_status, 'paid')
		self.assertEqual(len(mail.outbox), 1)
		self.assertIn('Completed', mail.outbox[0].body)

	# ---- payments
	def _sign(self, order_id, payment_id):
		return hmac.new(b'unit-test-secret', f'{order_id}|{payment_id}'.encode(), hashlib.sha256).hexdigest()

	def test_online_payment_flow(self):
		self._login_buyer()
		self._add_to_cart(1)
		with mock.patch('stock.payments.create_order', return_value='order_TEST123') as create:
			r = self.client.post(reverse('payment'), {'delivery_addr': 'Delhi', 'payment_method': 'online'})
		create.assert_called_once()
		self.assertEqual(create.call_args[0][0], 2000)
		self.assertContains(r, 'order_TEST123')
		self.assertContains(r, 'checkout.razorpay.com')
		self.assertEqual(Order.objects.get().status, Order.ORDER_STATE_WAITING)

		# a forged signature is rejected
		self.client.post(reverse('payment_verify'), {'razorpay_order_id': 'order_TEST123',
		                                             'razorpay_payment_id': 'pay_1', 'razorpay_signature': 'bad'})
		self.assertEqual(Order.objects.get().status, Order.ORDER_STATE_WAITING)

		r = self.client.post(reverse('payment_verify'), {
			'razorpay_order_id': 'order_TEST123', 'razorpay_payment_id': 'pay_1',
			'razorpay_signature': self._sign('order_TEST123', 'pay_1')})
		self.assertRedirects(r, reverse('profile'))
		order = Order.objects.get()
		self.assertEqual((order.status, order.payment_method, order.payment_status, order.gateway_payment_id),
		                 (Order.ORDER_STATE_PLACED, 'online', 'paid', 'pay_1'))
		self.art.refresh_from_db()
		self.assertEqual(self.art.quantity, 4)

		# cancelling a paid order flags a refund
		self.client.post(reverse('cancel_order', args=[order.O_id]))
		order.refresh_from_db()
		self.assertEqual(order.payment_status, Order.PAYMENT_REFUND_DUE)

	@override_settings(RAZORPAY_KEY_ID='', RAZORPAY_KEY_SECRET='')
	def test_online_option_hidden_without_keys(self):
		self._login_buyer()
		self._add_to_cart(1)
		r = self.client.get(reverse('payment'))
		self.assertNotContains(r, 'value="online"')
		r = self.client.post(reverse('payment'), {'delivery_addr': 'Delhi', 'payment_method': 'online'})
		self.assertEqual(r.status_code, 200)
		self.assertEqual(Order.objects.get().status, Order.ORDER_STATE_WAITING)

	# ---- email verification & password reset
	def test_signup_sends_verification_and_link_verifies(self):
		self.client.post(reverse('sign_up_customer'), {'username': 'fresh', 'email': 'fresh@example.com',
		                                               'password': 'Very-Strong-123', 'password1': 'Very-Strong-123'})
		self.assertEqual(len(mail.outbox), 1)
		path = re.search(r'(/verify-email/\S+)', mail.outbox[0].body).group(1)
		self.client.get(path)
		self.assertTrue(User.objects.get(username='fresh').email_verified)

	def test_bad_verification_link(self):
		self.client.get(reverse('verify_email', args=['MQ', 'bad-token']))
		self.assertFalse(User.objects.filter(email_verified=True).exists())

	def test_duplicate_email_rejected(self):
		r = self.client.post(reverse('sign_up_customer'), {'username': 'dupe', 'email': 'BUYER@example.com',
		                                                   'password': 'Very-Strong-123', 'password1': 'Very-Strong-123'})
		self.assertContains(r, 'already exists')

	def test_password_reset_email(self):
		r = self.client.post(reverse('password_reset'), {'email': 'buyer@example.com'})
		self.assertRedirects(r, reverse('password_reset_done'))
		self.assertEqual(len(mail.outbox), 1)
		self.assertIn('/password-reset/', mail.outbox[0].body)
		link = re.search(r'(/password-reset/[^/\s]+/[^/\s]+/)', mail.outbox[0].body).group(1)
		r = self.client.get(link, follow=True)
		self.assertContains(r, 'Choose a new password')

	# ---- artist extras
	def test_extra_images_bio_and_chart(self):
		self.client.login(username='painter2', password='s3cret-pass!')
		r = self.client.post(reverse('edit_art', args=[self.art.Art_id]), {
			'name': 'Monsoon', 'descrip': 'Oil', 'price': 2000, 'quantity': 5, 'category': Art.CATEGORY_NATURE,
			'medium': 'Oil', 'size': '24 x 36 in', 'year': 2024,
			'extra_images': [_jpeg((800, 600)), _jpeg((800, 600), (10, 10, 10))],
		})
		self.assertRedirects(r, reverse('aprofile'))
		self.assertEqual(self.art.extra_images.count(), 2)
		page = self.client.get(reverse('Art', args=[self.art.Art_id]))
		self.assertContains(page, 'class="thumb-btn', count=3)
		self.assertContains(page, '24 x 36 in')

		first = self.art.extra_images.first()
		self.client.post(reverse('edit_art', args=[self.art.Art_id]), {
			'name': 'Monsoon', 'descrip': 'Oil', 'price': 2000, 'quantity': 5, 'category': Art.CATEGORY_NATURE,
			'remove_image': [first.pk]})
		self.assertEqual(self.art.extra_images.count(), 1)

		self.client.post(reverse('aupdate', args=[self.artist_user.id]), {
			'name': 'Meera Artist', 'email': 'painter@example.com', 'phone': '1', 'address': 'Pune',
			'bio': 'I paint rain.', 'photo': _jpeg((1200, 1200))})
		self.artist.refresh_from_db()
		self.assertTrue(self.artist.photo)
		with Image.open(self.artist.photo.path) as im:
			self.assertLessEqual(max(im.size), 600)
		self.assertContains(self.client.get(reverse('artist_public', args=[self.artist.pk])), 'I paint rain.')

		Order.objects.create(Art_id=self.art, orderedBy=self.buyer, quantity=1, total_amount=2000,
		                     delivery_addr='x', status=Order.ORDER_STATE_PLACED)
		r = self.client.get(reverse('aprofile'))
		chart = r.context['chart']
		self.assertEqual(len(chart), 12)
		self.assertEqual(chart[-1]['value'], 2000)
		self.assertEqual(r.context['chart_max'], 2000)
		self.assertContains(r, 'Monthly revenue')
