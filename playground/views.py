import json
import stripe
from django.conf import settings
from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.core.mail import send_mail
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from .models import Purchase, CustomUser
from .forms import  RegisterForm
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy
from django.contrib.auth.views import PasswordResetView
from django.contrib.messages.views import SuccessMessageMixin
from datetime import date, datetime

stripe.api_key = settings.STRIPE_SECRET_KEY
endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

TIER_1_PRODUCT_ID = 'prod_OGo2FSiIDbqxiJ'
TIER_1_PRICE_ID = 'price_1NUGQABx0R9n4Zp1H1xaDmkQ' 

TIER_2_PRODUCT_ID = 'prod_OHZGl2v3Ou85os'
TIER_2_PRICE_ID = 'price_1NV07UBx0R9n4Zp1cDlSXJvs'

LOC_DOMAIN = 'http://localhost:8000'


def home(request):
    return render(request, 'home.html')


def sign_up(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('/home')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = RegisterForm()

    return render(request, 'signup.html', {"form": form})

@login_required
def account_page(request):
    user = request.user
    user_profile = CustomUser.objects.get(username=user)
    purchase_history = Purchase.objects.filter(user_name=user)

    return render(request, 'account.html', {'user_profile': user_profile, 'purchase_history': purchase_history})

@login_required
def change_password(request):
    if request.method == 'POST':
        old_password = request.POST.get('old_password')
        new_password = request.POST.get('changed_password')

        if old_password == new_password:
            messages.error(request, 'Old password and new password cannot be the same.')
        # Validate old password and update the password
        elif request.user.check_password(old_password):
            request.user.set_password(new_password)
            request.user.save()
            messages.success(request, 'Password change successful! Please click on "Back to Login" and re-login with your new password.')
        else:
            messages.error(request, 'Incorrect old password. Please try again.')

    return render(request, 'change-password.html')

from django.urls import reverse_lazy
from django.contrib.auth.views import PasswordResetView
from django.contrib.messages.views import SuccessMessageMixin

class ResetPasswordView(SuccessMessageMixin, PasswordResetView):
    template_name = 'password_reset_custom.html'
    email_template_name = 'password_reset_email.html'
    #subject_template_name = 'password_reset_subject'
    # success_message = "We've emailed you instructions for setting your password, " \
    #                   "if an account exists with the email you entered. You should receive them shortly." \
    #                   " If you don't receive an email, " \
    #                   "please make sure you've entered the address you registered with, and check your spam folder."
    success_url = reverse_lazy('password_reset_sent')


def reset_sent(request):
    return render(request, 'password_reset_sent.html')

def pricing(request):
    return render(request, 'pricing.html')

def services(request):
    return render(request, 'services.html')

def hireUs(request):
    return render(request, 'hire-us.html')

def helpCenter(request):
    return render(request, 'help-center.html')

def contacts(request):
    return render(request, 'contacts.html')

def about(request):
    return render(request, 'about.html')

def privacy(request):
    return render(request, 'privacy.html')

def termsOfUse(request):
    return render(request, 'terms-of-use.html')

def paymentPage(request):
    return render(request, 'paymentpage.html')

def checkoutT1(request):
    try:
        checkout_session = stripe.checkout.Session.create(
            line_items=[
                {
                    'price': TIER_1_PRICE_ID,
                    'quantity': 1,
                },
            ],
            metadata = {
                        'product_id': TIER_1_PRODUCT_ID, 
                        'product_name':'Tier 1', 
                        'price':'49.99'
                        },
            mode='payment',
            success_url=LOC_DOMAIN + '/success',
            cancel_url=LOC_DOMAIN + '/cancel',
        )
    except Exception as e:
        return str(e)
    return redirect(checkout_session.url, code=303)

@login_required
def checkoutT2(request):
    user = request.user
    try:
        checkout_session = stripe.checkout.Session.create(
            line_items=[
                {
                    'price': TIER_2_PRICE_ID,
                    'quantity': 1,
                },
            ],
            metadata = {
                        'product_id': TIER_2_PRODUCT_ID, 
                        'product_name':'Tier 2', 
                        'price':99.0,
                        'my_client': user
                        },
            mode='payment',
            success_url=LOC_DOMAIN + '/success',
            cancel_url=LOC_DOMAIN + '/cancel',
        )


    except Exception as e:
        return str(e)
    
    return redirect(checkout_session.url, code=303)

@csrf_exempt
def webhook_view(request):
    payload = request.body
    event = None

    try:
        event = json.loads(payload)
    except Exception as e:
        print('⚠️  Webhook error while parsing basic request.' + str(e))
        return JsonResponse({'success': False})

    if endpoint_secret:
        # Only verify the event if there is an endpoint secret defined
        # Otherwise use the basic event deserialized with json
        sig_header = request.headers.get('stripe-signature')
        try:
            event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
            )
        except stripe.error.SignatureVerificationError as e:
            print('⚠️  Webhook signature verification failed.' + str(e))
            return JsonResponse({'success': False})
    
    # Handle the checkout.session.completed event
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']

            customer_email = session["customer_details"]["email"]
            customer_name = session["customer_details"]["name"]
            timestamp = session["created"]
            client_name = session["metadata"]["my_client"]
            product_name = session["metadata"]["product_name"]
            price = session["metadata"]["price"]

            subject = f'Hello {customer_name}!'
            message = f'Thank you for your purchase of our {product_name} service'
            from_email = 'aluo.e28@gmail.com',
            recipient_list = [customer_email,]

            send_mail(subject, message, from_email, recipient_list)

            purchase = Purchase.objects.create(
                user_name=client_name,
                item_name=product_name,
                amount_paid=price,
                date_of_purchase = date.fromtimestamp(timestamp),
                time_of_purchase = datetime.fromtimestamp(timestamp).strftime("%H:%M:%S")
            )

            
    return HttpResponse(status=200)

def success(request):
    return render(request, 'success.html')

def cancel(request):
    return render(request, 'cancel.html')