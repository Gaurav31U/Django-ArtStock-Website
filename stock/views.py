from functools import wraps

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import (
    ArtForm,
    ArtistForm,
    ArtistSignUpForm,
    CheckoutForm,
    ContactUsForm,
    CustomerForm,
    CustomerSignUpForm,
)
from .models import Art, Artist, Customer, Order

SORT_OPTIONS = {
    'newest': '-Art_id',
    'price_low': 'price',
    'price_high': '-price',
    'name': 'name',
}

ARTIST_STATUS_FLOW = [
    Order.ORDER_STATE_ACKNOWLEDGED,
    Order.ORDER_STATE_DISPATCHED,
    Order.ORDER_STATE_COMPLETED,
]


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


def _cart_items(customer):
    return Order.objects.filter(orderedBy=customer, status=Order.ORDER_STATE_WAITING).select_related('Art_id', 'Art_id__Artist_id')


def _cart_summary(customer):
    items = list(_cart_items(customer))
    for item in items:
        item.line_total = item.Art_id.price * item.quantity
    total = sum(i.line_total for i in items)
    return items, total


# ---------------------------------------------------------------- gallery

def index_view(request):
    query = request.GET.get('search', '').strip()
    category = request.GET.get('category', '').strip()
    sort = request.GET.get('sort', 'newest')

    arts = Art.objects.select_related('Artist_id')
    if query:
        arts = arts.filter(
            Q(name__icontains=query) | Q(category__icontains=query)
            | Q(descrip__icontains=query) | Q(Artist_id__name__icontains=query)
        ).distinct()
    if category:
        arts = arts.filter(category=category)
    arts = arts.order_by(SORT_OPTIONS.get(sort, '-Art_id'))

    stats = cache.get('gallery_stats')
    if stats is None:
        stats = {
            'artworks': Art.objects.count(),
            'artists': Artist.objects.count(),
            'categories': Art.objects.values('category').distinct().count(),
        }
        cache.set('gallery_stats', stats, 300)

    categories = [c for c, _ in Art.CATEGORY_STATE_CHOICES]
    context = {
        'arts': arts,
        'query': query,
        'category': category,
        'sort': sort,
        'categories': categories,
        'stats': stats,
        'show_hero': not (query or category),
    }
    return render(request, 'base.html', context)


def Art_view(request, Art_id):
    art = get_object_or_404(Art.objects.select_related('Artist_id'), Art_id=Art_id)
    related = (Art.objects.filter(Q(category=art.category) | Q(Artist_id=art.Artist_id))
               .exclude(Art_id=art.Art_id).select_related('Artist_id')[:4])
    return render(request, 'Art.html', {'view': art, 'related': related})


def artist_public_view(request, pk):
    artist = get_object_or_404(Artist, pk=pk)
    arts = Art.objects.filter(Artist_id=artist)
    return render(request, 'artist_public.html', {'artist': artist, 'arts': arts})


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
    context = {'form': signup_form, 'mode': 'login', 'next': request.POST.get('next') or request.GET.get('next', ''), **AUTH_PAGES[role]}

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
        messages.success(request, 'Account created! Tell us a little about yourself.')
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
    return render(request, 'profile.html', {'customer': customer, 'orders': orders})


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

    form = CheckoutForm(request.POST or None, initial={'delivery_addr': customer.address})
    if request.method == 'POST' and form.is_valid():
        address = form.cleaned_data['delivery_addr']
        with transaction.atomic():
            problems = []
            for item in items:
                art = Art.objects.select_for_update().get(pk=item.Art_id.pk)
                if art.quantity < item.quantity:
                    problems.append(art.name)
            if problems:
                messages.error(request, 'Not enough stock for: ' + ', '.join(problems) + '. Please update your cart.')
                return redirect('Cart')
            for item in items:
                Art.objects.filter(pk=item.Art_id.pk).update(quantity=F('quantity') - item.quantity)
                item.status = Order.ORDER_STATE_PLACED
                item.delivery_addr = address
                item.total_amount = item.line_total
                item.save()
        cache.delete('gallery_stats')
        messages.success(request, 'Order placed! You will pay on delivery.')
        return redirect('profile')

    return render(request, 'Payment.html', {'items': items, 'total': total, 'count': len(items), 'form': form})


@customer_required
@require_POST
def cancel_order(request, O_id):
    order = get_object_or_404(Order, O_id=O_id, orderedBy=request.user.customer)
    if order.status in (Order.ORDER_STATE_PLACED, Order.ORDER_STATE_ACKNOWLEDGED):
        with transaction.atomic():
            Art.objects.filter(pk=order.Art_id_id).update(quantity=F('quantity') + order.quantity)
            order.status = Order.ORDER_STATE_CANCELLED
            order.save()
        messages.info(request, f'Order #{order.O_id} cancelled.')
    else:
        messages.error(request, 'This order can no longer be cancelled.')
    return redirect('profile')


# ---------------------------------------------------------------- artist

def createartist(request):
    if not request.user.is_authenticated or not request.user.is_artist:
        return _redirect_to_login(request, 'login_artist', 'Please sign in as an artist.')
    if hasattr(request.user, 'artist'):
        return redirect('aupdate', id=request.user.id)
    form = ArtistForm(request.POST or None, initial={'email': request.user.email})
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
    form = ArtistForm(request.POST or None, instance=request.user.artist)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Profile updated.')
        return redirect('aprofile')
    return render(request, 'artist_profile_form.html', {'form': form, 'title': 'Edit artist profile',
                                                        'subtitle': 'Keep your contact details current.'})


@artist_required
def artistProfile(request):
    artist = request.user.artist
    arts = Art.objects.filter(Artist_id=artist).annotate(
        sold=Sum('order__quantity', filter=Q(order__status__in=[
            Order.ORDER_STATE_PLACED, Order.ORDER_STATE_ACKNOWLEDGED,
            Order.ORDER_STATE_DISPATCHED, Order.ORDER_STATE_COMPLETED])),
    )
    sales = (Order.objects.filter(Art_id__Artist_id=artist)
             .exclude(status__in=[Order.ORDER_STATE_WAITING])
             .select_related('Art_id', 'orderedBy'))
    active_sales = sales.exclude(status=Order.ORDER_STATE_CANCELLED)
    summary = active_sales.aggregate(revenue=Sum('total_amount'), pieces=Sum('quantity'), orders=Count('O_id'))
    return render(request, 'artistprofile.html', {
        'artist': artist, 'arts': arts, 'sales': sales, 'summary': summary,
        'status_flow': ARTIST_STATUS_FLOW,
    })


@artist_required
def Add_Art_view(request):
    form = ArtForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        art = form.save(commit=False)
        art.Artist_id = request.user.artist
        art.save()
        cache.delete('gallery_stats')
        messages.success(request, f'“{art.name}” is now live in the gallery.')
        return redirect('aprofile')
    return render(request, 'artform.html', {'form': form, 'title': 'Add new artwork',
                                            'subtitle': 'Upload a clear photo and set a fair price.'})


@artist_required
def edit_art_view(request, Art_id):
    art = get_object_or_404(Art, Art_id=Art_id, Artist_id=request.user.artist)
    form = ArtForm(request.POST or None, request.FILES or None, instance=art)
    form.fields['image'].required = False
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Artwork updated.')
        return redirect('aprofile')
    return render(request, 'artform.html', {'form': form, 'title': f'Edit “{art.name}”',
                                            'subtitle': 'Leave the image empty to keep the current one.', 'art': art})


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
        order.status = new_status
        order.save()
        messages.success(request, f'Order #{order.O_id} marked as {new_status}.')
    else:
        messages.error(request, 'That status change is not allowed.')
    return redirect('aprofile')
