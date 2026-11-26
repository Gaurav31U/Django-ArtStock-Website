from datetime import date
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Count, F, OuterRef, Q, Subquery, Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.http import require_POST

from . import emails, payments
from .forms import (
    ArtForm,
    ArtistForm,
    ArtistSignUpForm,
    CheckoutForm,
    ContactUsForm,
    CustomerForm,
    CustomerSignUpForm,
    ReviewForm,
)
from .models import Art, Artist, ArtImage, Order, Review, Wishlist

PAGE_SIZE = 12

SORT_OPTIONS = {
    'newest': '-Art_id',
    'price_low': 'price',
    'price_high': '-price',
    'name': 'name',
    'rating': '-avg_rating',
}

ARTIST_STATUS_FLOW = [
    Order.ORDER_STATE_ACKNOWLEDGED,
    Order.ORDER_STATE_DISPATCHED,
    Order.ORDER_STATE_COMPLETED,
]

SOLD_STATES = [Order.ORDER_STATE_PLACED, Order.ORDER_STATE_ACKNOWLEDGED,
               Order.ORDER_STATE_DISPATCHED, Order.ORDER_STATE_COMPLETED]


# ---------------------------------------------------------------- helpers

def _redirect_to_login(request, url_name, message):
    messages.info(request, message)
    return redirect(f"{reverse(url_name)}?next={request.get_full_path()}")


def customer_required(view):
    """Signed-in customer with a completed profile."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return _redirect_to_login(request, 'login_customer', 'Please sign in as a customer to continue.')
        if not user.is_customer:
            messages.error(request, 'That page is only for customer accounts.')
            return redirect('index')
        if not hasattr(user, 'customer'):
            messages.info(request, 'Add your delivery details before shopping.')
            return redirect('cprofile')
        return view(request, *args, **kwargs)
    return wrapper


def artist_required(view):
    """Signed-in artist with a completed profile."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return _redirect_to_login(request, 'login_artist', 'Please sign in as an artist to continue.')
        if not user.is_artist:
            messages.error(request, 'That page is only for artist accounts.')
            return redirect('index')
        if not hasattr(user, 'artist'):
            messages.info(request, 'Complete your artist profile first.')
            return redirect('acreate')
        return view(request, *args, **kwargs)
    return wrapper


def _safe_next(request, default):
    nxt = request.POST.get('next') or request.GET.get('next')
    if nxt and nxt.startswith('/') and not nxt.startswith('//'):
        return nxt
    return default


def _int_or_none(value):
    try:
        return int(value) if value not in (None, '') else None
    except (TypeError, ValueError):
        return None


def _with_ratings(qs):
    return qs.annotate(avg_rating=Avg('reviews__rating'), review_count=Count('reviews', distinct=True))


def _wishlist_ids(request):
    user = request.user
    if user.is_authenticated and user.is_customer and hasattr(user, 'customer'):
        return set(Wishlist.objects.filter(customer=user.customer).values_list('art_id', flat=True))
    return set()


def _cart_items(customer):
    return (Order.objects.filter(orderedBy=customer, status=Order.ORDER_STATE_WAITING)
            .select_related('Art_id', 'Art_id__Artist_id'))


def _cart_summary(customer):
    items = list(_cart_items(customer))
    for item in items:
        item.line_total = item.Art_id.price * item.quantity
    total = sum(i.line_total for i in items)
    return items, total


def _stock_problems(items):
    problems = []
    for item in items:
        art = Art.objects.select_for_update().get(pk=item.Art_id.pk)
        if art.quantity < item.quantity:
            problems.append(art.name)
    return problems


def _place_orders(customer, items, address, method, gateway_order_id='', gateway_payment_id=''):
    """Turn cart rows into real orders and take the pieces out of stock. Returns None on success,
    or the list of artwork names that no longer have enough stock."""
    with transaction.atomic():
        problems = _stock_problems(items)
        if problems:
            return problems
        for item in items:
            Art.objects.filter(pk=item.Art_id.pk).update(quantity=F('quantity') - item.quantity)
            item.status = Order.ORDER_STATE_PLACED
            item.delivery_addr = address
            item.total_amount = item.Art_id.price * item.quantity
            item.payment_method = method
            item.payment_status = Order.PAYMENT_PAID if method == Order.PAYMENT_ONLINE else Order.PAYMENT_PENDING
            item.gateway_order_id = gateway_order_id
            item.gateway_payment_id = gateway_payment_id
            item.save()
    cache.delete('gallery_stats')
    emails.order_placed(customer, items)
    return None


# ---------------------------------------------------------------- gallery

def index_view(request):
    query = request.GET.get('search', '').strip()
    category = request.GET.get('category', '').strip()
    sort = request.GET.get('sort', 'newest')
    min_price = _int_or_none(request.GET.get('min_price'))
    max_price = _int_or_none(request.GET.get('max_price'))

    arts = _with_ratings(Art.objects.select_related('Artist_id'))
    if query:
        arts = arts.filter(
            Q(name__icontains=query) | Q(category__icontains=query) | Q(medium__icontains=query)
            | Q(descrip__icontains=query) | Q(Artist_id__name__icontains=query)
        )
    if category:
        arts = arts.filter(category=category)
    if min_price is not None:
        arts = arts.filter(price__gte=min_price)
    if max_price is not None:
        arts = arts.filter(price__lte=max_price)
    order = SORT_OPTIONS.get(sort, '-Art_id')
    arts = arts.order_by(F('avg_rating').desc(nulls_last=True), '-Art_id') if sort == 'rating' else arts.order_by(order)

    page = Paginator(arts, PAGE_SIZE).get_page(request.GET.get('page'))

    stats = cache.get('gallery_stats')
    if stats is None:
        stats = {
            'artworks': Art.objects.count(),
            'artists': Artist.objects.count(),
            'categories': Art.objects.values('category').distinct().count(),
        }
        cache.set('gallery_stats', stats, 300)

    params = request.GET.copy()
    params.pop('page', None)
    filtered = bool(query or category or min_price is not None or max_price is not None)
    context = {
        'arts': page,
        'page': page,
        'page_query': params.urlencode(),
        'query': query,
        'category': category,
        'sort': sort,
        'min_price': min_price,
        'max_price': max_price,
        'categories': [c for c, _ in Art.CATEGORY_STATE_CHOICES],
        'stats': stats,
        'show_hero': not filtered and page.number == 1,
        'filtered': filtered,
        'wishlist_ids': _wishlist_ids(request),
    }
    return render(request, 'base.html', context)


def Art_view(request, Art_id):
    art = get_object_or_404(_with_ratings(Art.objects.select_related('Artist_id')), Art_id=Art_id)
    related = _with_ratings(
        Art.objects.filter(Q(category=art.category) | Q(Artist_id=art.Artist_id))
        .exclude(Art_id=art.Art_id).select_related('Artist_id'))[:4]
    reviews = art.reviews.select_related('customer')

    can_review = False
    my_review = None
    user = request.user
    if user.is_authenticated and user.is_customer and hasattr(user, 'customer'):
        can_review = Order.objects.filter(Art_id=art, orderedBy=user.customer,
                                          status=Order.ORDER_STATE_COMPLETED).exists()
        my_review = reviews.filter(customer=user.customer).first()

    return render(request, 'Art.html', {
        'view': art,
        'related': related,
        'gallery': [art.image] + [x.image for x in art.extra_images.all()],
        'reviews': reviews,
        'can_review': can_review,
        'review_form': ReviewForm(instance=my_review),
        'my_review': my_review,
        'wishlist_ids': _wishlist_ids(request),
    })


def artist_public_view(request, pk):
    artist = get_object_or_404(Artist, pk=pk)
    arts = _with_ratings(Art.objects.filter(Artist_id=artist).select_related('Artist_id'))
    rating = Review.objects.filter(art__Artist_id=artist).aggregate(avg=Avg('rating'), count=Count('id'))
    return render(request, 'artist_public.html', {
        'artist': artist, 'arts': arts, 'rating': rating, 'wishlist_ids': _wishlist_ids(request),
    })


def ContactUs_view(request):
    form = ContactUsForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Thanks for reaching out! We'll get back to you soon.")
        return redirect('ContactUs')
    return render(request, 'Contact.html', {'form': form})


# ---------------------------------------------------------------- auth

AUTH_PAGES = {
    'customer': {
        'art_image': '5.jpg', 'role_label': 'Collector', 'headline': 'Find a piece that speaks to you.',
        'blurb': 'Save artwork to your cart, check out in seconds and follow every order to your door.',
        'login_url': 'login_customer', 'signup_url': 'sign_up_customer', 'switch_url': 'login_artist',
        'switch_text': 'Are you an artist?', 'switch_link': 'Go to the artist studio →',
    },
    'artist': {
        'art_image': '1.jpg', 'role_label': 'Artist', 'headline': 'Your studio, open to the world.',
        'blurb': 'List your work, set your price and track every sale from one simple dashboard.',
        'login_url': 'login_artist', 'signup_url': 'sign_up_artist', 'switch_url': 'login_customer',
        'switch_text': 'Looking to buy art?', 'switch_link': 'Collector sign in →',
    },
}


def logouts(request):
    logout(request)
    messages.success(request, 'You have been signed out.')
    return redirect('index')


def _login(request, role):
    is_artist = role == 'artist'
    template = 'SignArtist.html' if is_artist else 'SignCustomer.html'
    signup_form = (ArtistSignUpForm if is_artist else CustomerSignUpForm)()
    context = {'form': signup_form, 'mode': 'login',
               'next': request.POST.get('next') or request.GET.get('next', ''), **AUTH_PAGES[role]}

    if request.method == 'POST':
        user = authenticate(request, username=request.POST.get('username', ''),
                            password=request.POST.get('password', ''))
        if user is None:
            context['error_message'] = 'Invalid username or password.'
        elif is_artist and not user.is_artist:
            context['error_message'] = 'This account is not registered as an artist.'
        elif not is_artist and not user.is_customer:
            context['error_message'] = 'This account is not registered as a customer.'
        else:
            login(request, user)
            messages.success(request, f'Welcome back, {user.username}!')
            return redirect(_safe_next(request, reverse('aprofile' if is_artist else 'index')))
    return render(request, template, context)


def _signup(request, role):
    is_artist = role == 'artist'
    template = 'SignArtist.html' if is_artist else 'SignCustomer.html'
    form = (ArtistSignUpForm if is_artist else CustomerSignUpForm)(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        emails.verify_email(user)
        messages.success(request, f'Account created! We sent a confirmation link to {user.email}.')
        return redirect('acreate' if is_artist else 'cprofile')
    return render(request, template, {'form': form, 'mode': 'signup', **AUTH_PAGES[role]})


def login_customer_request(request):
    return _login(request, 'customer')


def sign_up_customer_request(request):
    return _signup(request, 'customer')


def login_artist_request(request):
    return _login(request, 'artist')


def sign_up_artist_request(request):
    return _signup(request, 'artist')


def verify_email_view(request, uidb64, token):
    User = get_user_model()
    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uidb64)))
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        user = None
    if user is not None and user.email_verified:
        messages.info(request, 'Your email is already confirmed.')
    elif user is not None and emails.email_verification_token.check_token(user, token):
        user.email_verified = True
        user.save(update_fields=['email_verified'])
        messages.success(request, 'Email confirmed. Thank you!')
    else:
        messages.error(request, 'That confirmation link is invalid or has expired.')
    return redirect('index')


@require_POST
def resend_verification(request):
    if not request.user.is_authenticated:
        return redirect('login_customer')
    if request.user.email_verified:
        messages.info(request, 'Your email is already confirmed.')
    elif not request.user.email:
        messages.error(request, 'Add an email address to your account first.')
    else:
        emails.verify_email(request.user)
        messages.success(request, f'Confirmation link sent to {request.user.email}.')
    return redirect(_safe_next(request, reverse('index')))


# ---------------------------------------------------------------- customer

def createCustomer(request):
    if not request.user.is_authenticated or not request.user.is_customer:
        return _redirect_to_login(request, 'login_customer', 'Please sign in as a customer.')
    if hasattr(request.user, 'customer'):
        return redirect('cupdate', id=request.user.id)
    form = CustomerForm(request.POST or None, initial={'email': request.user.email})
    if request.method == 'POST' and form.is_valid():
        instance = form.save(commit=False)
        instance.user = request.user
        instance.save()
        messages.success(request, 'Profile saved. Happy collecting!')
        return redirect('profile')
    return render(request, 'profileform.html', {'form': form, 'title': 'Your details',
                                                'subtitle': 'We use these to deliver your artwork.'})


@customer_required
def customerProfile(request):
    customer = request.user.customer
    orders = (Order.objects.filter(orderedBy=customer).exclude(status=Order.ORDER_STATE_WAITING)
              .select_related('Art_id'))
    reviewed = set(Review.objects.filter(customer=customer).values_list('art_id', flat=True))
    return render(request, 'profile.html', {'customer': customer, 'orders': orders, 'reviewed': reviewed})


@customer_required
def updateCustomer(request, id=None):
    form = CustomerForm(request.POST or None, instance=request.user.customer)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Profile updated.')
        return redirect('profile')
    return render(request, 'profileform.html', {'form': form, 'title': 'Edit profile',
                                                'subtitle': 'Keep your delivery details up to date.'})


@customer_required
def wishlist_view(request):
    items = (Wishlist.objects.filter(customer=request.user.customer)
             .select_related('art', 'art__Artist_id'))
    arts = _with_ratings(Art.objects.filter(pk__in=[i.art_id for i in items]).select_related('Artist_id'))
    return render(request, 'wishlist.html', {'arts': arts, 'wishlist_ids': {a.pk for a in arts}})


@customer_required
@require_POST
def toggle_wishlist(request, Art_id):
    art = get_object_or_404(Art, Art_id=Art_id)
    item, created = Wishlist.objects.get_or_create(customer=request.user.customer, art=art)
    if created:
        messages.success(request, f'Saved “{art.name}” to your wishlist.')
    else:
        item.delete()
        messages.info(request, f'Removed “{art.name}” from your wishlist.')
    return redirect(_safe_next(request, reverse('wishlist')))


@customer_required
@require_POST
def add_review(request, Art_id):
    art = get_object_or_404(Art, Art_id=Art_id)
    customer = request.user.customer
    if not Order.objects.filter(Art_id=art, orderedBy=customer, status=Order.ORDER_STATE_COMPLETED).exists():
        messages.error(request, 'You can review a piece once your order for it has been delivered.')
        return redirect('Art', Art_id=art.Art_id)
    existing = Review.objects.filter(art=art, customer=customer).first()
    form = ReviewForm(request.POST, instance=existing)
    if form.is_valid():
        review = form.save(commit=False)
        review.art = art
        review.customer = customer
        review.save()
        messages.success(request, 'Thanks for your review!' if existing is None else 'Review updated.')
    else:
        messages.error(request, 'Please choose a star rating.')
    return redirect(reverse('Art', args=[art.Art_id]) + '#reviews')


@customer_required
def add_to_cart(request, Art_id):
    art = get_object_or_404(Art, Art_id=Art_id)
    try:
        qty = max(1, int(request.POST.get('quantity', 1)))
    except (TypeError, ValueError):
        qty = 1

    if art.quantity < 1:
        messages.error(request, f'Sorry, “{art.name}” is sold out.')
        return redirect('Art', Art_id=art.Art_id)

    customer = request.user.customer
    item = Order.objects.filter(Art_id=art, orderedBy=customer, status=Order.ORDER_STATE_WAITING).first()
    if item:
        item.quantity = min(item.quantity + qty, art.quantity)
    else:
        item = Order(Art_id=art, orderedBy=customer, delivery_addr=customer.address,
                     quantity=min(qty, art.quantity))
    item.total_amount = art.price * item.quantity
    item.save()
    messages.success(request, f'Added “{art.name}” to your cart.')
    return redirect(_safe_next(request, reverse('Cart')))


@customer_required
@require_POST
def update_cart(request, O_id):
    item = get_object_or_404(Order, O_id=O_id, orderedBy=request.user.customer, status=Order.ORDER_STATE_WAITING)
    try:
        qty = int(request.POST.get('quantity', item.quantity))
    except (TypeError, ValueError):
        qty = item.quantity
    if qty < 1:
        item.delete()
        messages.info(request, 'Item removed from your cart.')
    else:
        item.quantity = min(qty, item.Art_id.quantity) or 1
        item.total_amount = item.Art_id.price * item.quantity
        item.save()
    return redirect('Cart')


@customer_required
@require_POST
def remove_from_cart(request, O_id):
    item = get_object_or_404(Order, O_id=O_id, orderedBy=request.user.customer, status=Order.ORDER_STATE_WAITING)
    item.delete()
    messages.info(request, 'Item removed from your cart.')
    return redirect('Cart')


@customer_required
def MyCart_view(request):
    items, total = _cart_summary(request.user.customer)
    return render(request, 'cart.html', {'items': items, 'total': total, 'count': len(items)})


@customer_required
def payment_view(request):
    customer = request.user.customer
    items, total = _cart_summary(customer)
    if not items:
        messages.info(request, 'Your cart is empty.')
        return redirect('Cart')

    online = payments.is_enabled()
    form = CheckoutForm(request.POST or None, online_enabled=online,
                        initial={'delivery_addr': customer.address})
    if request.method == 'POST' and form.is_valid():
        address = form.cleaned_data['delivery_addr']

        if form.cleaned_data['payment_method'] == Order.PAYMENT_ONLINE:
            with transaction.atomic():
                problems = _stock_problems(items)
            if problems:
                messages.error(request, 'Not enough stock for: ' + ', '.join(problems) + '. Please update your cart.')
                return redirect('Cart')
            try:
                gateway_order_id = payments.create_order(total, receipt=f'cust{customer.pk}-{items[0].O_id}')
            except payments.PaymentError:
                messages.error(request, 'We could not reach the payment gateway. Try again or pay on delivery.')
                return redirect('payment')
            request.session['pending_payment'] = {
                'gateway_order_id': gateway_order_id,
                'address': address,
                'item_ids': [i.O_id for i in items],
                'amount': total,
            }
            return render(request, 'pay.html', {
                'items': items, 'total': total, 'key_id': settings.RAZORPAY_KEY_ID,
                'gateway_order_id': gateway_order_id, 'amount_paise': total * 100, 'customer': customer,
            })

        problems = _place_orders(customer, items, address, Order.PAYMENT_COD)
        if problems:
            messages.error(request, 'Not enough stock for: ' + ', '.join(problems) + '. Please update your cart.')
            return redirect('Cart')
        messages.success(request, 'Order placed! You will pay on delivery.')
        return redirect('profile')

    return render(request, 'Payment.html', {'items': items, 'total': total, 'count': len(items),
                                            'form': form, 'online_enabled': online})


@customer_required
@require_POST
def payment_verify(request):
    pending = request.session.get('pending_payment')
    gateway_order_id = request.POST.get('razorpay_order_id', '')
    payment_id = request.POST.get('razorpay_payment_id', '')
    signature = request.POST.get('razorpay_signature', '')
    if not pending or pending['gateway_order_id'] != gateway_order_id \
            or not payments.verify_signature(gateway_order_id, payment_id, signature):
        messages.error(request, 'We could not confirm that payment. You have not been charged for any order.')
        return redirect('payment')

    customer = request.user.customer
    items = list(_cart_items(customer).filter(O_id__in=pending['item_ids']))
    del request.session['pending_payment']
    problems = _place_orders(customer, items, pending['address'], Order.PAYMENT_ONLINE,
                             gateway_order_id=gateway_order_id, gateway_payment_id=payment_id)
    if problems:
        messages.error(request, f'Payment {payment_id} went through, but some items sold out meanwhile. '
                                'Please contact us for a refund.')
        return redirect('ContactUs')
    messages.success(request, 'Payment received and order placed. Thank you!')
    return redirect('profile')


@customer_required
@require_POST
def cancel_order(request, O_id):
    order = get_object_or_404(Order, O_id=O_id, orderedBy=request.user.customer)
    if order.status in (Order.ORDER_STATE_PLACED, Order.ORDER_STATE_ACKNOWLEDGED):
        with transaction.atomic():
            Art.objects.filter(pk=order.Art_id_id).update(quantity=F('quantity') + order.quantity)
            order.status = Order.ORDER_STATE_CANCELLED
            if order.payment_status == Order.PAYMENT_PAID:
                order.payment_status = Order.PAYMENT_REFUND_DUE
            order.save()
        emails.order_status_changed(order)
        note = ' Your refund will be processed shortly.' if order.payment_status == Order.PAYMENT_REFUND_DUE else ''
        messages.info(request, f'Order #{order.O_id} cancelled.{note}')
    else:
        messages.error(request, 'This order can no longer be cancelled.')
    return redirect('profile')


# ---------------------------------------------------------------- artist

def createartist(request):
    if not request.user.is_authenticated or not request.user.is_artist:
        return _redirect_to_login(request, 'login_artist', 'Please sign in as an artist.')
    if hasattr(request.user, 'artist'):
        return redirect('aupdate', id=request.user.id)
    form = ArtistForm(request.POST or None, request.FILES or None, initial={'email': request.user.email})
    if request.method == 'POST' and form.is_valid():
        instance = form.save(commit=False)
        instance.user = request.user
        instance.save()
        messages.success(request, 'Artist profile created. Time to upload your first piece!')
        return redirect('aprofile')
    return render(request, 'artist_profile_form.html', {'form': form, 'title': 'Complete your artist profile',
                                                        'subtitle': 'Buyers will see your name on every artwork.'})


@artist_required
def updateartist(request, id=None):
    form = ArtistForm(request.POST or None, request.FILES or None, instance=request.user.artist)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Profile updated.')
        return redirect('aprofile')
    return render(request, 'artist_profile_form.html', {'form': form, 'title': 'Edit artist profile',
                                                        'subtitle': 'Your bio and photo appear on your public page.'})


def _monthly_revenue(artist, months=12):
    """Revenue per calendar month for the last `months` months, oldest first, zeros included."""
    today = date.today()
    y, m = today.year, today.month
    keys = []
    for _ in range(months):
        keys.append((y, m))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    keys.reverse()
    start = date(keys[0][0], keys[0][1], 1)
    rows = (Order.objects.filter(Art_id__Artist_id=artist, status__in=SOLD_STATES, timestamp__date__gte=start)
            .annotate(month=TruncMonth('timestamp')).values('month').annotate(total=Sum('total_amount')))
    totals = {(r['month'].year, r['month'].month): r['total'] for r in rows}
    data = [{'label': date(y, m, 1).strftime('%b'), 'year': y, 'value': totals.get((y, m), 0)} for y, m in keys]
    peak = max((d['value'] for d in data), default=0)
    axis_max = _nice_ceiling(peak)
    peak_index = max(range(len(data)), key=lambda i: (data[i]['value'], i)) if peak else None
    for i, d in enumerate(data):
        d['pct'] = round(d['value'] / axis_max * 100, 1) if axis_max else 0
        d['is_peak'] = i == peak_index  # label only the latest highest month
    return data, axis_max


def _axis_ticks(axis_max):
    """Top/mid/zero labels for the revenue axis, all in one unit (₹, K or L)."""
    if axis_max >= 100_000:
        div, unit = 100_000, 'L'
    elif axis_max >= 1_000:
        div, unit = 1_000, 'K'
    else:
        div, unit = 1, ''

    def fmt(v):
        n = v / div
        text = f'{n:.1f}'.rstrip('0').rstrip('.')
        return f'₹{text}{unit}' if v else '₹0'
    return [fmt(axis_max), fmt(axis_max / 2), fmt(0)]


def _nice_ceiling(value):
    """Round up to 1, 2, 2.5 or 5 x 10^n so axis ticks are clean numbers."""
    if value <= 0:
        return 0
    magnitude = 10 ** (len(str(int(value))) - 1)
    for step in (1, 2, 2.5, 5, 10):
        if value <= step * magnitude:
            return int(step * magnitude)
    return int(10 * magnitude)


@artist_required
def artistProfile(request):
    artist = request.user.artist
    sold_subquery = (Order.objects.filter(Art_id=OuterRef('pk'), status__in=SOLD_STATES)
                     .values('Art_id').annotate(s=Sum('quantity')).values('s'))
    arts = _with_ratings(Art.objects.filter(Artist_id=artist)).annotate(sold=Subquery(sold_subquery))
    sales = (Order.objects.filter(Art_id__Artist_id=artist)
             .exclude(status__in=[Order.ORDER_STATE_WAITING])
             .select_related('Art_id', 'orderedBy'))
    active_sales = sales.exclude(status=Order.ORDER_STATE_CANCELLED)
    summary = active_sales.aggregate(revenue=Sum('total_amount'), pieces=Sum('quantity'), orders=Count('O_id'))
    rating = Review.objects.filter(art__Artist_id=artist).aggregate(avg=Avg('rating'), count=Count('id'))
    chart, chart_max = _monthly_revenue(artist)
    ticks = _axis_ticks(chart_max)
    closed = (Order.ORDER_STATE_COMPLETED, Order.ORDER_STATE_CANCELLED)
    sales = list(sales)
    return render(request, 'artistprofile.html', {
        'artist': artist, 'arts': arts, 'summary': summary, 'rating': rating,
        'open_sales': [o for o in sales if o.status not in closed],
        'past_sales': [o for o in sales if o.status in closed],
        'status_flow': ARTIST_STATUS_FLOW, 'chart': chart, 'chart_max': chart_max, 'chart_ticks': ticks,
        'chart_has_data': any(d['value'] for d in chart),
    })


def _save_extra_images(art, files):
    for f in files:
        ArtImage.objects.create(art=art, image=f)


@artist_required
def Add_Art_view(request):
    form = ArtForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        art = form.save(commit=False)
        art.Artist_id = request.user.artist
        art.save()
        _save_extra_images(art, form.cleaned_data.get('extra_images') or [])
        cache.delete('gallery_stats')
        messages.success(request, f'“{art.name}” is now live in the gallery.')
        return redirect('aprofile')
    return render(request, 'artform.html', {'form': form, 'title': 'Add new artwork',
                                            'subtitle': 'Upload clear photos and set a fair price.'})


@artist_required
def edit_art_view(request, Art_id):
    art = get_object_or_404(Art, Art_id=Art_id, Artist_id=request.user.artist)
    form = ArtForm(request.POST or None, request.FILES or None, instance=art)
    form.fields['image'].required = False
    if request.method == 'POST' and form.is_valid():
        form.save()
        _save_extra_images(art, form.cleaned_data.get('extra_images') or [])
        remove_ids = request.POST.getlist('remove_image')
        if remove_ids:
            for img in ArtImage.objects.filter(art=art, pk__in=remove_ids):
                img.image.delete(save=False)
                img.delete()
        messages.success(request, 'Artwork updated.')
        return redirect('aprofile')
    return render(request, 'artform.html', {'form': form, 'title': f'Edit “{art.name}”',
                                            'subtitle': 'Leave the main image empty to keep the current one.',
                                            'art': art, 'extra_images': art.extra_images.all()})


@artist_required
@require_POST
def delete_art_view(request, Art_id):
    art = get_object_or_404(Art, Art_id=Art_id, Artist_id=request.user.artist)
    name = art.name
    art.delete()
    cache.delete('gallery_stats')
    messages.info(request, f'“{name}” was removed.')
    return redirect('aprofile')


@artist_required
@require_POST
def update_order_status(request, O_id):
    order = get_object_or_404(Order, O_id=O_id, Art_id__Artist_id=request.user.artist)
    new_status = request.POST.get('status')
    if new_status in ARTIST_STATUS_FLOW and order.status not in (Order.ORDER_STATE_CANCELLED, Order.ORDER_STATE_COMPLETED):
        changed = order.status != new_status
        order.status = new_status
        if new_status == Order.ORDER_STATE_COMPLETED and order.payment_method == Order.PAYMENT_COD:
            order.payment_status = Order.PAYMENT_PAID
        order.save()
        if changed:
            emails.order_status_changed(order)
        messages.success(request, f'Order #{order.O_id} marked as {new_status}.')
    else:
        messages.error(request, 'That status change is not allowed.')
    return redirect('aprofile')
