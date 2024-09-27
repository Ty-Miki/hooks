from django.urls import path
from .views import create_checkout_session, stripe_webhook

app_name = 'payment'

urlpatterns = [
    path('create-checkout-session/<str:plan_type>/', create_checkout_session, name='create-checkout-session'),
    path('webhook/', stripe_webhook, name='stripe-webhook'),
]
