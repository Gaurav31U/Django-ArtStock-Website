from .models import Order


def cart_count(request):
	"""Number of items in the signed-in customer's cart, for the nav badge."""
	user = getattr(request, 'user', None)
	if not user or not user.is_authenticated or not user.is_customer:
		return {'cart_count': 0}
	customer = getattr(user, 'customer', None)
	if customer is None:
		return {'cart_count': 0}
	return {'cart_count': Order.objects.filter(orderedBy=customer, status=Order.ORDER_STATE_WAITING).count()}
