import stripe
from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from account.models import Profile

stripe.api_key = settings.CREDENTIALS['STRIPE_SECRET_KEY']

def create_checkout_session(request, plan_type):
    # Change this to domain when deployed
    DOMAIN = "http://0.0.0.0:8000"
    prices = {
        'starter': 'price_1PzFWeEt5xiNvM25sbfARSfP',
        'pro': 'price_1PzFUcEt5xiNvM25KM2MdEKv',
        'exclusive': 'price_1PzFWeEt5xiNvM25sbfARSfP'
    }

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[
                {
                    'price': prices[plan_type],
                    'quantity': 1,
                },
            ],
            mode='subscription',
            success_url=DOMAIN + reverse('success') + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=DOMAIN + reverse('cancel'),
        )
        return redirect(checkout_session.url, code=303)
    except Exception as e:
        return str(e)

@csrf_exempt
def stripe_webhook(request):
    payload = request.body.decode('utf-8')
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    event = None

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.CREDENTIALS['STRIPE_WEBHOOK_SECRET']
        )
    except ValueError as e:
        return JsonResponse({'status': 'invalid payload'}, status=400)
    except stripe.error.SignatureVerificationError as e:
        return JsonResponse({'status': 'invalid signature'}, status=400)

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        handle_checkout_session(session)

    return JsonResponse({'status': 'success'}, status=200)

def handle_checkout_session(session):
    customer_id = session['customer']
    
    # Fetch or create user based on Stripe customer ID
    try:
        user = User.objects.get(stripe_customer_id=customer_id)
    except User.DoesNotExist:
       # Create a new user if one does not exist
        # You can generate a username and email based on the session info or some default value
        email = session.get('customer_email', f'{customer_id}@example.com')
        username = email.split('@')[0]  # Basic example, you can customize it
        
        user = User.objects.create(
            username=username,
            email=email,
            stripe_customer_id=customer_id
        )
    
    # Check if the user profile exists and has a credits field
    if not hasattr(user, 'profile'):
        # Create a profile if it doesn't exist
        Profile.objects.create(user=user, credits=0)  # Assuming Profile model has a credits field
        user.refresh_from_db()  # Refresh the user object to include the new profile

    # Initialize credits if they are not set
    if user.profile.credits is None:
        user.profile.credits = 0
    if user.profile.merge_credits is None:
        user.profile.merge_credits = 0

    # Determine credits based on plan
    plan_credits = {
        'price_1PzFWeEt5xiNvM25sbfARSfP': 50,   # starter
        'price_1PzFUcEt5xiNvM25KM2MdEKv': 120,  # pro
        'price_1PzFWeEt5xiNvM25sbfARSfP': 300   # exclusive
    }

    plan_merge_credits = {
        'price_1PzFWeEt5xiNvM25sbfARSfP': 300,   # starter
        'price_1PzFUcEt5xiNvM25KM2MdEKv': 600,  # pro
        'price_1PzFWeEt5xiNvM25sbfARSfP': 1500   # exclusive
    }

    price_id = session['line_items']['data'][0]['price']['id']
    credits = plan_credits.get(price_id, 0)
    merge_credits = plan_merge_credits.get(price_id, 0)
    user.profile.credits += credits
    user.profile.merge_credits += merge_credits
    user.profile.save()