from django.shortcuts import render
from django.contrib.auth.views import LoginView
from .forms import CustomLoginForm
from django.conf import settings
from django.contrib import messages
from django.urls import reverse_lazy

# Create your views here.

def home(request):
    STRIPE_PUBLISHER_KEY = settings.CREDENTIALS['STRIPE_PUBLISHER_KEY']
    return render(request,
                  'home.html',
                  {'STRIPE_PUBLISHER_KEY': STRIPE_PUBLISHER_KEY})

class CustomLoginView(LoginView):
    form_class = CustomLoginForm
    template_name = 'registration/login.html'

    # # Custom behavior after a successful login
    # def form_valid(self, form):
    #     messages.success(self.request, 'You have successfully logged in.')
    #     return super().form_valid(form)
    
    # Custom behavior after a failed login
    def form_invalid(self, form):
        messages.error(self.request, 'Invalid email or password. Please try again.')
        return super().form_invalid(form)
    
    def get_success_url(self):
        return reverse_lazy('hooks:upload')  # Redirect to the hooks upload page after login