from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Art, ArtImage, Artist, ContactUs, Customer, Order, Review, User, Wishlist


@admin.register(User)
class ArtStockUserAdmin(UserAdmin):
	list_display = ('username', 'email', 'is_customer', 'is_artist', 'email_verified', 'is_staff')
	list_filter = ('is_customer', 'is_artist', 'email_verified', 'is_staff')
	fieldsets = UserAdmin.fieldsets + (('Role', {'fields': ('is_customer', 'is_artist', 'email_verified')}),)


@admin.register(Artist)
class ArtistAdmin(admin.ModelAdmin):
	list_display = ('name', 'email', 'phone', 'date')
	search_fields = ('name', 'email')


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
	list_display = ('name', 'email', 'phone', 'date')
	search_fields = ('name', 'email')


class ArtImageInline(admin.TabularInline):
	model = ArtImage
	extra = 0


@admin.register(Art)
class ArtAdmin(admin.ModelAdmin):
	inlines = [ArtImageInline]
	list_display = ('name', 'Artist_id', 'category', 'price', 'quantity')
	list_filter = ('category',)
	search_fields = ('name', 'descrip')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
	list_display = ('O_id', 'Art_id', 'orderedBy', 'quantity', 'total_amount', 'status', 'payment_method',
	                'payment_status', 'timestamp')
	list_filter = ('status', 'payment_method', 'payment_status')
	search_fields = ('gateway_order_id', 'gateway_payment_id')


@admin.register(ContactUs)
class ContactUsAdmin(admin.ModelAdmin):
	list_display = ('firstname', 'lastname', 'email', 'phone', 'created_at')


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
	list_display = ('art', 'customer', 'rating', 'created_at')
	list_filter = ('rating',)


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
	list_display = ('customer', 'art', 'added_at')
