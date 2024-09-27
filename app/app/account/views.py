from django.shortcuts import render
from django.contrib.auth.views import LoginView
from .forms import CustomLoginForm
from django.conf import settings

# Create your views here.

def home(request):
    STRIPE_PUBLISHER_KEY = settings.CREDENTIALS['STRIPE_PUBLISHER_KEY']
    return render(request,
                  'home.html',
                  {'STRIPE_PUBLISHER_KEY': STRIPE_PUBLISHER_KEY})

class CustomLoginView(LoginView):
    form_class = CustomLoginForm
    template_name = 'registration/login.html'