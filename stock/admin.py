from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Art, Artist, ContactUs, Customer, Order, User


@admin.register(User)
class ArtStockUserAdmin(UserAdmin):
	list_display = ('username', 'email', 'is_customer', 'is_artist', 'is_staff')
	list_filter = ('is_customer', 'is_artist', 'is_staff')
	fieldsets = UserAdmin.fieldsets + (('Role', {'fields': ('is_customer', 'is_artist')}),)


@admin.register(Artist)
class ArtistAdmin(admin.ModelAdmin):
	list_display = ('name', 'email', 'phone', 'date')
	search_fields = ('name', 'email')


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
	list_display = ('name', 'email', 'phone', 'date')
	search_fields = ('name', 'email')


@admin.register(Art)
class ArtAdmin(admin.ModelAdmin):
	list_display = ('name', 'Artist_id', 'category', 'price', 'quantity')
	list_filter = ('category',)
	search_fields = ('name', 'descrip')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
	list_display = ('O_id', 'Art_id', 'orderedBy', 'quantity', 'total_amount', 'status', 'timestamp')
	list_filter = ('status',)


@admin.register(ContactUs)
class ContactUsAdmin(admin.ModelAdmin):
	list_display = ('firstname', 'lastname', 'email', 'phone', 'created_at')
