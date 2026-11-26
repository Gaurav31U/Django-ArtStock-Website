from django.contrib.auth import views as auth_views
from django.urls import path

from stock import views

urlpatterns = [
    path('', views.index_view, name="index"),
    path('ContactUs', views.ContactUs_view, name="ContactUs"),
    path('Art/<int:Art_id>', views.Art_view, name="Art"),
    path('Art/<int:Art_id>/review', views.add_review, name="add_review"),
    path('artists/<int:pk>', views.artist_public_view, name="artist_public"),

    path('login/customer', views.login_customer_request, name="login_customer"),
    path('login/signup/customer', views.sign_up_customer_request, name="sign_up_customer"),
    path('customer/cprofile', views.createCustomer, name="cprofile"),
    path('customer/profile', views.customerProfile, name="profile"),
    path('user/update/<int:id>', views.updateCustomer, name='cupdate'),
    path('wishlist', views.wishlist_view, name="wishlist"),
    path('wishlist/<int:Art_id>/toggle', views.toggle_wishlist, name="toggle_wishlist"),
    path('AddtoCart/<int:Art_id>', views.add_to_cart, name="Add_to_Cart"),
    path('MyCart', views.MyCart_view, name="Cart"),
    path('MyCart/<int:O_id>/update', views.update_cart, name="update_cart"),
    path('MyCart/<int:O_id>/remove', views.remove_from_cart, name="remove_from_cart"),
    path('payment', views.payment_view, name="payment"),
    path('payment/verify', views.payment_verify, name="payment_verify"),
    path('orders/<int:O_id>/cancel', views.cancel_order, name="cancel_order"),

    path('login/artist', views.login_artist_request, name="login_artist"),
    path('signup/artist', views.sign_up_artist_request, name="sign_up_artist"),
    path('artist/create', views.createartist, name='acreate'),
    path('artist/update/<int:id>', views.updateartist, name='aupdate'),
    path('profile/artist', views.artistProfile, name='aprofile'),
    path('artist/addart', views.Add_Art_view, name="addart"),
    path('artist/art/<int:Art_id>/edit', views.edit_art_view, name="edit_art"),
    path('artist/art/<int:Art_id>/delete', views.delete_art_view, name="delete_art"),
    path('artist/orders/<int:O_id>/status', views.update_order_status, name="update_order_status"),

    path('verify-email/<uidb64>/<token>', views.verify_email_view, name="verify_email"),
    path('verify-email/resend', views.resend_verification, name="resend_verification"),
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='registration/reset_form.html',
        email_template_name='emails/password_reset.txt',
        subject_template_name='emails/password_reset_subject.txt'), name='password_reset'),
    path('password-reset/sent/', auth_views.PasswordResetDoneView.as_view(
        template_name='registration/reset_done.html'), name='password_reset_done'),
    path('password-reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='registration/reset_confirm.html'), name='password_reset_confirm'),
    path('password-reset/complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='registration/reset_complete.html'), name='password_reset_complete'),

    path('logout', views.logouts, name="logouts"),
]
