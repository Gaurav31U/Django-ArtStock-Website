# ArtStock: an e-commerce site for buying and selling art

[![CI](https://github.com/Gaurav31U/Django-ArtStock-Website/actions/workflows/ci.yml/badge.svg)](https://github.com/Gaurav31U/Django-ArtStock-Website/actions/workflows/ci.yml)

ArtStock is a Django-based online art gallery. Artists open a studio, list their work and track sales. Collectors browse, save favourites, check out (online or pay on delivery), follow their orders and review what they bought.

![ArtStock home page](screenshots/home.png)

## Features

**For collectors**
- Gallery search (title, artist, medium, description), category filters, a price range, sorting (newest, price, top rated, A–Z) and pagination
- Artwork pages with a photo gallery, medium, size and year, stock status, star ratings and related works
- **Wishlist**: save pieces with the heart button and find them later under *Saved*
- Cart with quantity steppers, then checkout with **Razorpay online payment** (UPI, cards, net banking) or **pay on delivery**
- Order history with payment status and tracking. Orders can be cancelled before dispatch, and paid ones are flagged for refund
- **Verified reviews**: only collectors whose order was delivered can rate and review a piece
- **Email notifications** when an order is placed and when its status changes

**For artists**
- Studio dashboard showing revenue, orders, pieces sold, average rating and a **monthly revenue chart** (with a table view)
- Upload artwork with **several photos** plus medium, size and year. Edit details, add or remove photos, or delete artwork
- Open-orders queue: move orders through *Acknowledged → Dispatched → Completed* (buyers are emailed at each step)
- Public artist page with **bio, profile photo** and overall rating

**Accounts and platform**
- Separate sign-in for collectors and artists, **email verification** and **password reset**
- **Automatic image optimisation**: uploads are resized (max 1600 px) and get a 600 px thumbnail for cards. `python manage.py optimize_images` backfills older images
- Production-ready: Gunicorn, WhiteNoise static files, PostgreSQL through `DATABASE_URL`, HTTPS security settings, Docker, a Render blueprint and GitHub Actions CI
- Prometheus metrics at `/metrics`, plus optional Redis caching

## Screenshots

| Gallery | Filters and price range |
|---|---|
| ![Gallery](screenshots/gallery.png) | ![Filtered gallery](screenshots/gallery-filters.png) |

| Artwork with photo gallery | Verified reviews |
|---|---|
| ![Artwork detail](screenshots/art-detail.png) | ![Reviews](screenshots/reviews.png) |

| Wishlist | Cart |
|---|---|
| ![Wishlist](screenshots/wishlist.png) | ![Cart](screenshots/cart.png) |

| Checkout (online or on delivery) | Collector orders |
|---|---|
| ![Checkout](screenshots/checkout.png) | ![Collector account](screenshots/customer-profile.png) |

| Artist studio | Monthly revenue chart |
|---|---|
| ![Artist studio](screenshots/artist-studio.png) | ![Sales chart](screenshots/sales-chart.png) |

| Public artist page | Edit artwork |
|---|---|
| ![Artist page](screenshots/artist-public.png) | ![Edit artwork](screenshots/edit-artwork.png) |

| Sign in | Password reset |
|---|---|
| ![Sign in](screenshots/login.png) | ![Password reset](screenshots/password-reset.png) |

| Write a review | Contact |
|---|---|
| ![Write a review](screenshots/write-review.png) | ![Contact](screenshots/contact.png) |

| Mobile: home | Mobile: artwork |
|---|---|
| <img src="screenshots/mobile-home.png" alt="Mobile home" width="300"> | <img src="screenshots/mobile-detail.png" alt="Mobile artwork" width="300"> |

## Running locally

Requires Python 3.10+.

```
git clone https://github.com/Gaurav31U/Django-ArtStock-Website.git
cd Django-ArtStock-Website
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000). Run `python manage.py createsuperuser` to get an admin account at `/admin/`.

You don't need any other services locally:
- **Database:** SQLite (`db.sqlite3`)
- **Cache:** in-memory
- **Email:** printed in the terminal running `runserver`, so you can click verification and reset links from there
- **Payments:** only *pay on delivery* is offered until you add Razorpay keys

### Turning on online payments

1. Create a free account at [razorpay.com](https://razorpay.com) and switch the dashboard to **Test mode**.
2. Generate test keys (they start with `rzp_test_`).
3. Set `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET`, then restart the server. *Pay online* now appears at checkout. In test mode you can pay with Razorpay's test cards and UPI IDs.

### Configuration

Copy `.env.example` to `.env`, or set these as environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `DJANGO_SECRET_KEY` | dev-only key | **Required** when `DJANGO_DEBUG=False` |
| `DJANGO_DEBUG` | `True` | Set to `False` in production |
| `DJANGO_ALLOWED_HOSTS` | `*` | Comma-separated host list |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | empty | e.g. `https://artstock.example.com` |
| `SITE_URL` | `http://127.0.0.1:8000` | Base URL used in email links |
| `DATABASE_URL` | SQLite | e.g. `postgres://user:pass@host:5432/artstock` |
| `REDIS_URL` | unset | e.g. `redis://redis:6379/1` |
| `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` | empty | Turn on online payment |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` | console backend | SMTP for real email |
| `DEFAULT_FROM_EMAIL` | `ArtStock <no-reply@artstock.local>` | Sender address |
| `DJANGO_MEDIA_ROOT` | `./media` | Where uploads are stored |
| `DJANGO_SERVE_MEDIA` | `True` | Let Django serve uploads (turn off if a CDN or bucket serves them) |

### Tests

```
python manage.py test stock
```

The suite (30 tests) covers the cart and checkout, Razorpay signature verification (with the gateway mocked), emails, reviews, the wishlist, image processing, password reset and email verification. CI runs it on SQLite and PostgreSQL, and also checks that the Docker image builds.

## Docker

Run the whole stack (Django on Gunicorn, PostgreSQL, Redis, Prometheus, Grafana, Loki):

```
docker compose up --build
```

| Service | URL |
|---|---|
| ArtStock | http://localhost:8000 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 |

On start, the container applies migrations and builds any missing thumbnails. Uploads and the database are kept in named volumes.

## Deploying to Render

The repo includes a [`render.yaml`](render.yaml) blueprint:

1. Push the repo to GitHub.
2. In Render, choose **New → Blueprint** and pick the repository. It creates the web service, a PostgreSQL database and a 1 GB disk for uploads.
3. In the service's **Environment** tab, set `SITE_URL` to your Render URL. Optionally add the Razorpay keys and SMTP settings.
4. Open a shell on the service and run `python manage.py createsuperuser`.

`render.yaml` uses the paid *starter* plan, because the free plan has no persistent disk and uploaded images would be lost on every deploy. Any other Docker host works the same way: set the environment variables above and run the image.

## Contributing

1. Fork the repository.
2. Create a new branch (`git checkout -b feature/YourFeature`).
3. Commit your changes (`git commit -m 'Add some feature'`).
4. Push to the branch (`git push origin feature/YourFeature`).
5. Open a pull request. CI runs the tests automatically.

## Contact

For questions or issues, email [gaurav319288@gmail.com](mailto:gaurav319288@gmail.com).
