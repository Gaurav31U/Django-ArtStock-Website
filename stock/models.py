import datetime

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from .images import optimise_image, make_thumbnail


class User(AbstractUser):
	is_customer = models.BooleanField(default=False)
	is_artist = models.BooleanField(default=False)
	email_verified = models.BooleanField(default=False)


class Artist(models.Model):
	user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
	name = models.CharField(max_length=50, blank=False)
	email = models.EmailField(max_length=254, blank=False)
	phone = models.CharField(max_length=15)
	address = models.TextField()
	date = models.DateField(default=datetime.date.today)
	bio = models.TextField(blank=True, help_text='A few lines about you and your practice.')
	photo = models.ImageField(upload_to='artists/', blank=True)

	def __str__(self):
		return self.name

	def save(self, *args, **kwargs):
		if self.photo and not getattr(self.photo, '_committed', True):
			optimise_image(self.photo, max_size=600)
		super().save(*args, **kwargs)


class Customer(models.Model):
	user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
	name = models.CharField(max_length=50, blank=False)
	email = models.EmailField(max_length=254, blank=False)
	phone = models.CharField(max_length=15, blank=False)
	address = models.TextField()
	date = models.DateField(default=datetime.date.today)

	def __str__(self):
		return self.name


class Art(models.Model):
	Artist_id = models.ForeignKey(Artist, on_delete=models.CASCADE)
	Art_id = models.AutoField(primary_key=True)
	quantity = models.IntegerField(blank=False)
	name = models.CharField(max_length=50, blank=False)
	descrip = models.TextField(blank=False)
	price = models.PositiveIntegerField()
	image = models.ImageField(null=False, blank=False)
	thumbnail = models.ImageField(upload_to='thumbs/', blank=True, editable=False)
	size = models.CharField(max_length=60, blank=True, help_text='e.g. 30 x 40 inches')
	medium = models.CharField(max_length=80, blank=True, help_text='e.g. Acrylic on canvas')
	year = models.PositiveIntegerField(null=True, blank=True,
	                                   validators=[MinValueValidator(1000), MaxValueValidator(2100)])
	created_at = models.DateTimeField(auto_now_add=True, null=True)

	CATEGORY_GAMES		=	"Games"
	CATEGORY_FICTION	=	"Fiction"
	CATEGORY_NATURE		=	"Natures"
	CATEGORY_GEOMETRIC	=	"Geometric"
	CATEGORY_MYSTERIOUS	=	"Mysterious"
	CATEGORY_ACTORS		=	"Actors"
	CATEGORY_MULTIVERSE	=	"Multiverse"
	CATEGORY_COMICS		= 	"Comics"
	CATEGORY_REALISTIC	=	"Realistic"
	CATEGORY_CONCEPTUAL	=	"Conceptual"
	CATEGORY_ANCIENT	=	"Ancient"
	CATEGORY_OTHER		=	"Others"

	CATEGORY_STATE_CHOICES = (
		(CATEGORY_GAMES, CATEGORY_GAMES),
		(CATEGORY_FICTION, CATEGORY_FICTION),
		(CATEGORY_NATURE, CATEGORY_NATURE),
		(CATEGORY_GEOMETRIC, CATEGORY_GEOMETRIC),
		(CATEGORY_ACTORS, CATEGORY_ACTORS),
		(CATEGORY_MYSTERIOUS, CATEGORY_MYSTERIOUS),
		(CATEGORY_MULTIVERSE, CATEGORY_MULTIVERSE),
		(CATEGORY_COMICS, CATEGORY_COMICS),
		(CATEGORY_REALISTIC, CATEGORY_REALISTIC),
		(CATEGORY_CONCEPTUAL, CATEGORY_CONCEPTUAL),
		(CATEGORY_ANCIENT, CATEGORY_ANCIENT),
		(CATEGORY_OTHER, CATEGORY_OTHER),
	)

	category = models.CharField(max_length=20, choices=CATEGORY_STATE_CHOICES, default=CATEGORY_OTHER)

	class Meta:
		ordering = ['-Art_id']

	def __str__(self):
		return self.name

	@property
	def in_stock(self):
		return self.quantity > 0

	@property
	def thumb_url(self):
		"""Small version for cards and lists; falls back to the full image."""
		if self.thumbnail:
			return self.thumbnail.url
		return self.image.url

	def save(self, *args, **kwargs):
		new_upload = self.image and not getattr(self.image, '_committed', True)
		if new_upload:
			optimise_image(self.image, max_size=1600)
		super().save(*args, **kwargs)
		if new_upload or (self.image and not self.thumbnail):
			if make_thumbnail(self.image, self.thumbnail, size=600):
				super().save(update_fields=['thumbnail'])


class ArtImage(models.Model):
	"""Extra photos for an artwork (detail shots, framing, wall view)."""
	art = models.ForeignKey(Art, on_delete=models.CASCADE, related_name='extra_images')
	image = models.ImageField(upload_to='gallery/')
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['id']

	def save(self, *args, **kwargs):
		if self.image and not getattr(self.image, '_committed', True):
			optimise_image(self.image, max_size=1600)
		super().save(*args, **kwargs)


class Order(models.Model):
	O_id = models.AutoField(primary_key=True)
	Art_id = models.ForeignKey(Art, on_delete=models.CASCADE)
	orderedBy = models.ForeignKey(Customer, on_delete=models.CASCADE)
	total_amount = models.IntegerField(default=0)
	timestamp = models.DateTimeField(auto_now_add=True)
	delivery_addr = models.TextField()
	quantity = models.IntegerField(default=1)

	ORDER_STATE_WAITING 	 = "Waiting"
	ORDER_STATE_PLACED 		 = "Placed"
	ORDER_STATE_ACKNOWLEDGED = "Acknowledged"
	ORDER_STATE_COMPLETED    = "Completed"
	ORDER_STATE_CANCELLED    = "Cancelled"
	ORDER_STATE_DISPATCHED   = "Dispatched"

	ORDER_STATE_CHOICES = (
		(ORDER_STATE_WAITING, ORDER_STATE_WAITING),
		(ORDER_STATE_PLACED, ORDER_STATE_PLACED),
		(ORDER_STATE_ACKNOWLEDGED, ORDER_STATE_ACKNOWLEDGED),
		(ORDER_STATE_COMPLETED, ORDER_STATE_COMPLETED),
		(ORDER_STATE_CANCELLED, ORDER_STATE_CANCELLED),
		(ORDER_STATE_DISPATCHED, ORDER_STATE_DISPATCHED),
	)

	status = models.CharField(max_length=50, choices=ORDER_STATE_CHOICES, default=ORDER_STATE_WAITING)

	PAYMENT_COD = 'cod'
	PAYMENT_ONLINE = 'online'
	PAYMENT_METHOD_CHOICES = ((PAYMENT_COD, 'Pay on delivery'), (PAYMENT_ONLINE, 'Paid online'))
	PAYMENT_PENDING = 'pending'
	PAYMENT_PAID = 'paid'
	PAYMENT_REFUND_DUE = 'refund_due'
	PAYMENT_STATUS_CHOICES = (
		(PAYMENT_PENDING, 'Pending'), (PAYMENT_PAID, 'Paid'), (PAYMENT_REFUND_DUE, 'Refund due'),
	)
	payment_method = models.CharField(max_length=10, choices=PAYMENT_METHOD_CHOICES, default=PAYMENT_COD)
	payment_status = models.CharField(max_length=12, choices=PAYMENT_STATUS_CHOICES, default=PAYMENT_PENDING)
	gateway_order_id = models.CharField(max_length=64, blank=True)
	gateway_payment_id = models.CharField(max_length=64, blank=True)

	class Meta:
		ordering = ['-timestamp']

	def __str__(self):
		return str(self.O_id) + ' ' + self.status

	@property
	def unit_price(self):
		return self.Art_id.price


class Wishlist(models.Model):
	customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='wishlist')
	art = models.ForeignKey(Art, on_delete=models.CASCADE, related_name='wishlisted_by')
	added_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-added_at']
		constraints = [models.UniqueConstraint(fields=['customer', 'art'], name='unique_wishlist_item')]


class Review(models.Model):
	art = models.ForeignKey(Art, on_delete=models.CASCADE, related_name='reviews')
	customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='reviews')
	rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
	comment = models.TextField(blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-created_at']
		constraints = [models.UniqueConstraint(fields=['art', 'customer'], name='one_review_per_customer')]

	def __str__(self):
		return f'{self.rating}★ {self.art} by {self.customer}'


class ContactUs(models.Model):
	firstname = models.CharField(max_length=50)
	lastname = models.CharField(max_length=50)
	phone = models.CharField(max_length=14)
	email = models.EmailField(max_length=254)
	text = models.TextField()
	created_at = models.DateTimeField(auto_now_add=True, null=True)

	def __str__(self):
		return self.firstname + ' ' + self.lastname
