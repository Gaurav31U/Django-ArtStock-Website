import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Art, Artist, ContactUs, Customer, Order, User

# 1x1 transparent GIF
GIF = (b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,'
       b'\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;')

TEMP_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class ArtStockFlowTests(TestCase):
	@classmethod
	def tearDownClass(cls):
		super().tearDownClass()
		shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

	def setUp(self):
		self.artist_user = User.objects.create_user('painter', password='s3cret-pass!', is_artist=True)
		self.artist = Artist.objects.create(user=self.artist_user, name='Asha Painter', email='a@example.com',
		                                    phone='9999999999', address='Varanasi')
		self.art = Art.objects.create(Artist_id=self.artist, name='Ghat at Dawn', descrip='Acrylic', price=1500,
		                              quantity=3, category=Art.CATEGORY_NATURE,
		                              image=SimpleUploadedFile('a.gif', GIF, content_type='image/gif'))
		self.buyer_user = User.objects.create_user('buyer', password='s3cret-pass!', is_customer=True)
		self.buyer = Customer.objects.create(user=self.buyer_user, name='Ravi Buyer', email='b@example.com',
		                                     phone='8888888888', address='Lucknow')

	# ---- public pages
	def test_public_pages_render(self):
		for url in [reverse('index'), reverse('Art', args=[self.art.Art_id]), reverse('ContactUs'),
		            reverse('login_customer'), reverse('login_artist'), reverse('artist_public', args=[self.artist.pk])]:
			self.assertEqual(self.client.get(url).status_code, 200, url)

	def test_missing_art_is_404(self):
		self.assertEqual(self.client.get(reverse('Art', args=[999])).status_code, 404)

	def test_search_and_category_filter(self):
		r = self.client.get(reverse('index'), {'search': 'ghat'})
		self.assertContains(r, 'Ghat at Dawn')
		r = self.client.get(reverse('index'), {'search': 'asha'})
		self.assertContains(r, 'Ghat at Dawn')
		r = self.client.get(reverse('index'), {'category': Art.CATEGORY_COMICS})
		self.assertNotContains(r, 'Ghat at Dawn')

	def test_contact_form_saves(self):
		r = self.client.post(reverse('ContactUs'), {'firstname': 'A', 'lastname': 'B', 'phone': '123',
		                                            'email': 'x@example.com', 'text': 'Hello'})
		self.assertRedirects(r, reverse('ContactUs'))
		self.assertEqual(ContactUs.objects.count(), 1)

	# ---- auth
	def test_customer_signup_flow(self):
		r = self.client.post(reverse('sign_up_customer'), {'username': 'newbie', 'email': 'n@example.com',
		                                                   'password': 'Very-Strong-123', 'password1': 'Very-Strong-123'})
		self.assertRedirects(r, reverse('cprofile'))
		user = User.objects.get(username='newbie')
		self.assertTrue(user.is_customer)
		self.assertTrue(user.check_password('Very-Strong-123'))

	def test_signup_password_mismatch(self):
		r = self.client.post(reverse('sign_up_artist'), {'username': 'x', 'email': 'x@example.com',
		                                                 'password': 'Very-Strong-123', 'password1': 'nope'})
		self.assertEqual(r.status_code, 200)
		self.assertContains(r, 'Passwords do not match')

	def test_role_checked_on_login(self):
		r = self.client.post(reverse('login_artist'), {'username': 'buyer', 'password': 's3cret-pass!'})
		self.assertContains(r, 'not registered as an artist')

	def test_anonymous_add_to_cart_redirects_to_login(self):
		r = self.client.post(reverse('Add_to_Cart', args=[self.art.Art_id]))
		self.assertEqual(r.status_code, 302)
		self.assertIn(reverse('login_customer'), r['Location'])

	# ---- cart & checkout
	def test_cart_checkout_flow(self):
		self.client.login(username='buyer', password='s3cret-pass!')
		self.client.post(reverse('Add_to_Cart', args=[self.art.Art_id]), {'quantity': 2})
		item = Order.objects.get(orderedBy=self.buyer)
		self.assertEqual((item.quantity, item.total_amount, item.status), (2, 3000, Order.ORDER_STATE_WAITING))

		# adding again caps at available stock
		self.client.post(reverse('Add_to_Cart', args=[self.art.Art_id]), {'quantity': 5})
		item.refresh_from_db()
		self.assertEqual(item.quantity, 3)

		self.client.post(reverse('update_cart', args=[item.O_id]), {'quantity': 1})
		item.refresh_from_db()
		self.assertEqual((item.quantity, item.total_amount), (1, 1500))

		self.assertContains(self.client.get(reverse('Cart')), 'Ghat at Dawn')
		r = self.client.post(reverse('payment'), {'delivery_addr': 'New address'})
		self.assertRedirects(r, reverse('profile'))
		item.refresh_from_db()
		self.art.refresh_from_db()
		self.assertEqual(item.status, Order.ORDER_STATE_PLACED)
		self.assertEqual(item.delivery_addr, 'New address')
		self.assertEqual(self.art.quantity, 2)

		# cancelling restores stock
		self.client.post(reverse('cancel_order', args=[item.O_id]))
		item.refresh_from_db()
		self.art.refresh_from_db()
		self.assertEqual(item.status, Order.ORDER_STATE_CANCELLED)
		self.assertEqual(self.art.quantity, 3)

	def test_remove_from_cart(self):
		self.client.login(username='buyer', password='s3cret-pass!')
		self.client.post(reverse('Add_to_Cart', args=[self.art.Art_id]))
		item = Order.objects.get(orderedBy=self.buyer)
		self.client.post(reverse('remove_from_cart', args=[item.O_id]))
		self.assertFalse(Order.objects.exists())

	def test_sold_out_cannot_be_added(self):
		self.art.quantity = 0
		self.art.save()
		self.client.login(username='buyer', password='s3cret-pass!')
		self.client.post(reverse('Add_to_Cart', args=[self.art.Art_id]))
		self.assertFalse(Order.objects.exists())

	def test_customer_without_profile_sent_to_profile_form(self):
		User.objects.create_user('fresh', password='s3cret-pass!', is_customer=True)
		self.client.login(username='fresh', password='s3cret-pass!')
		self.assertRedirects(self.client.get(reverse('Cart')), reverse('cprofile'))

	# ---- artist studio
	def test_artist_dashboard_and_art_crud(self):
		self.client.login(username='painter', password='s3cret-pass!')
		self.assertContains(self.client.get(reverse('aprofile')), 'Ghat at Dawn')
		r = self.client.post(reverse('addart'), {
			'name': 'New Piece', 'descrip': 'Oil', 'price': 999, 'quantity': 1, 'category': Art.CATEGORY_ANCIENT,
			'image': SimpleUploadedFile('b.gif', GIF, content_type='image/gif'),
		})
		self.assertRedirects(r, reverse('aprofile'))
		new = Art.objects.get(name='New Piece')
		self.assertEqual(new.Artist_id, self.artist)

		r = self.client.post(reverse('edit_art', args=[new.Art_id]), {
			'name': 'Renamed', 'descrip': 'Oil', 'price': 1200, 'quantity': 1, 'category': Art.CATEGORY_ANCIENT})
		self.assertRedirects(r, reverse('aprofile'))
		new.refresh_from_db()
		self.assertEqual((new.name, new.price), ('Renamed', 1200))

		self.client.post(reverse('delete_art', args=[new.Art_id]))
		self.assertFalse(Art.objects.filter(pk=new.pk).exists())

	def test_artist_cannot_edit_others_art(self):
		other = User.objects.create_user('other', password='s3cret-pass!', is_artist=True)
		Artist.objects.create(user=other, name='Other', email='o@example.com', phone='1', address='x')
		self.client.login(username='other', password='s3cret-pass!')
		self.assertEqual(self.client.get(reverse('edit_art', args=[self.art.Art_id])).status_code, 404)

	def test_artist_updates_order_status(self):
		order = Order.objects.create(Art_id=self.art, orderedBy=self.buyer, quantity=1, total_amount=1500,
		                             delivery_addr='x', status=Order.ORDER_STATE_PLACED)
		self.client.login(username='painter', password='s3cret-pass!')
		self.client.post(reverse('update_order_status', args=[order.O_id]), {'status': Order.ORDER_STATE_DISPATCHED})
		order.refresh_from_db()
		self.assertEqual(order.status, Order.ORDER_STATE_DISPATCHED)
