from django import forms
from django.contrib.auth.password_validation import validate_password

from .models import Art, Artist, ContactUs, Customer, Order, Review, User


class StyledFormMixin:
	"""Adds the site's input class to every widget."""

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		for field in self.fields.values():
			widget = field.widget
			if isinstance(widget, (forms.RadioSelect, forms.CheckboxInput)):
				continue
			css = 'input'
			if isinstance(widget, forms.Select):
				css = 'input select'
			elif isinstance(widget, forms.ClearableFileInput):
				css = 'input file'
			widget.attrs.setdefault('class', css)


class MultipleFileInput(forms.ClearableFileInput):
	allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
	"""ImageField that accepts several files from one <input multiple>."""

	def __init__(self, *args, **kwargs):
		kwargs.setdefault('widget', MultipleFileInput(attrs={'accept': 'image/*'}))
		super().__init__(*args, **kwargs)

	def clean(self, data, initial=None):
		single = super().clean
		if isinstance(data, (list, tuple)):
			return [single(d, initial) for d in data if d]
		return [single(data, initial)] if data else []


class ContactUsForm(StyledFormMixin, forms.ModelForm):
	class Meta:
		model = ContactUs
		fields = ("firstname", "lastname", "phone", "email", "text")
		labels = {
			'firstname': 'First name',
			'lastname': 'Last name',
			'text': 'Message',
		}
		widgets = {'text': forms.Textarea(attrs={'rows': 5})}


class BaseSignUpForm(StyledFormMixin, forms.ModelForm):
	password = forms.CharField(widget=forms.PasswordInput)
	password1 = forms.CharField(widget=forms.PasswordInput, label='Confirm password')

	role_flag = None

	class Meta:
		model = User
		fields = ['username', 'email', 'password']

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.fields['email'].required = True

	def clean_email(self):
		email = self.cleaned_data['email'].strip()
		if User.objects.filter(email__iexact=email).exists():
			raise forms.ValidationError('An account with this email already exists.')
		return email

	def clean(self):
		cleaned = super().clean()
		password = cleaned.get('password')
		confirm = cleaned.get('password1')
		if password and confirm and password != confirm:
			self.add_error('password1', 'Passwords do not match.')
		if password:
			try:
				validate_password(password, self.instance)
			except forms.ValidationError as exc:
				self.add_error('password', exc)
		return cleaned

	def save(self, commit=True):
		user = super().save(commit=False)
		user.set_password(self.cleaned_data['password'])
		setattr(user, self.role_flag, True)
		if commit:
			user.save()
		return user


class CustomerSignUpForm(BaseSignUpForm):
	role_flag = 'is_customer'


class ArtistSignUpForm(BaseSignUpForm):
	role_flag = 'is_artist'


class CustomerForm(StyledFormMixin, forms.ModelForm):
	class Meta:
		model = Customer
		fields = ['name', 'email', 'phone', 'address']
		widgets = {'address': forms.Textarea(attrs={'rows': 3})}


class ArtistForm(StyledFormMixin, forms.ModelForm):
	class Meta:
		model = Artist
		fields = ['name', 'email', 'phone', 'photo', 'address', 'bio']
		labels = {'photo': 'Profile photo'}
		widgets = {
			'address': forms.Textarea(attrs={'rows': 3}),
			'bio': forms.Textarea(attrs={'rows': 4}),
		}


class ArtForm(StyledFormMixin, forms.ModelForm):
	extra_images = MultipleImageField(required=False, label='More photos',
	                                  help_text='Optional: detail shots, framing or a wall view. Select several at once.')

	class Meta:
		model = Art
		fields = ['name', 'category', 'descrip', 'price', 'quantity', 'medium', 'size', 'year', 'image']
		labels = {
			'descrip': 'Description',
			'price': 'Price (₹)',
			'quantity': 'Copies in stock',
			'image': 'Main image',
		}
		widgets = {'descrip': forms.Textarea(attrs={'rows': 4})}


class CheckoutForm(StyledFormMixin, forms.Form):
	delivery_addr = forms.CharField(label='Delivery address', widget=forms.Textarea(attrs={'rows': 3}))
	payment_method = forms.ChoiceField(choices=Order.PAYMENT_METHOD_CHOICES, initial=Order.PAYMENT_COD,
	                                   widget=forms.RadioSelect)

	def __init__(self, *args, online_enabled=False, **kwargs):
		super().__init__(*args, **kwargs)
		if not online_enabled:
			self.fields['payment_method'].choices = [(Order.PAYMENT_COD, 'Pay on delivery')]


class ReviewForm(StyledFormMixin, forms.ModelForm):
	rating = forms.TypedChoiceField(choices=[(i, i) for i in range(5, 0, -1)], coerce=int,
	                                widget=forms.RadioSelect)

	class Meta:
		model = Review
		fields = ['rating', 'comment']
		widgets = {'comment': forms.Textarea(attrs={'rows': 3, 'placeholder': 'What did you think of this piece?'})}
		labels = {'comment': 'Your review (optional)'}
