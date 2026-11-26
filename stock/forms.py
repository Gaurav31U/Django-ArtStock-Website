from django import forms
from django.contrib.auth.password_validation import validate_password

from .models import Art, Artist, ContactUs, Customer, User


class StyledFormMixin:
	"""Adds the site's input class to every widget."""

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		for field in self.fields.values():
			css = 'input'
			if isinstance(field.widget, forms.Select):
				css = 'input select'
			elif isinstance(field.widget, forms.ClearableFileInput):
				css = 'input file'
			field.widget.attrs.setdefault('class', css)


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
		fields = ['name', 'email', 'phone', 'address']
		widgets = {'address': forms.Textarea(attrs={'rows': 3})}


class ArtForm(StyledFormMixin, forms.ModelForm):
	class Meta:
		model = Art
		fields = ['name', 'category', 'descrip', 'price', 'quantity', 'image']
		labels = {
			'descrip': 'Description',
			'price': 'Price (₹)',
			'quantity': 'Copies in stock',
		}
		widgets = {'descrip': forms.Textarea(attrs={'rows': 4})}


class CheckoutForm(StyledFormMixin, forms.Form):
	delivery_addr = forms.CharField(label='Delivery address', widget=forms.Textarea(attrs={'rows': 3}))
