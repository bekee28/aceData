import logging

import stripe
from django.conf import settings
from django.shortcuts import render, redirect
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from .models import Purchase, CustomUser
from .forms import  RegisterForm
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.urls import reverse, reverse_lazy
from django.contrib.auth.views import PasswordResetView
from django.contrib.messages.views import SuccessMessageMixin
from django.db import IntegrityError
from datetime import date, datetime

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY
endpoint_secret = settings.STRIPE_WEBHOOK_SECRET


def home(request):
    return render(request, 'home.html')


def sign_up(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
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
    user_profile = user
    # Prefer the FK link; fall back to the denormalized username for legacy/guest rows.
    purchase_history = Purchase.objects.filter(
        Q(user=user) | Q(user_name=user.get_username())
    ).distinct().order_by('-date_of_purchase', '-time_of_purchase')

    return render(request, 'account.html', {'user_profile': user_profile, 'purchase_history': purchase_history})

@login_required
def change_password(request):
    if request.method == 'POST':
        old_password = request.POST.get('old_password') or ''
        new_password = request.POST.get('changed_password') or ''

        if not request.user.check_password(old_password):
            messages.error(request, 'Incorrect old password. Please try again.')
        elif not new_password:
            messages.error(request, 'Please enter a new password.')
        elif old_password == new_password:
            messages.error(request, 'Old password and new password cannot be the same.')
        else:
            # Enforce the same strength rules as signup before saving.
            try:
                validate_password(new_password, user=request.user)
            except DjangoValidationError as exc:
                for error in exc.messages:
                    messages.error(request, error)
            else:
                request.user.set_password(new_password)
                request.user.save()
                # Keep the current session valid after the password hash changes
                # so the user isn't silently logged out.
                update_session_auth_hash(request, request.user)
                messages.success(request, 'Password change successful! Your new password is now active.')

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

def contacts(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        company = request.POST.get('company', '').strip()
        body = request.POST.get('message', '').strip()

        if not (name and email and body):
            messages.error(request, 'Please fill in your name, email, and a message.')
        else:
            subject = f'New consultation request from {name}'
            lines = [f'Name: {name}', f'Email: {email}']
            if company:
                lines.append(f'Company: {company}')
            lines += ['', body]
            # Sends to the site owner. Surface failures instead of dropping the
            # lead silently — a misconfigured SMTP must not look like success.
            try:
                send_mail(
                    subject,
                    '\n'.join(lines),
                    settings.DEFAULT_FROM_EMAIL,
                    [settings.DEFAULT_FROM_EMAIL],
                    fail_silently=False,
                )
            except Exception:
                logger.exception('Contact form email failed to send.')
                messages.error(
                    request,
                    f"Sorry, we couldn't send your message right now. "
                    f"Please email us directly at {settings.DEFAULT_FROM_EMAIL}.",
                )
            else:
                messages.success(request, "Thanks! Your message has been sent. We'll be in touch shortly.")
        return redirect('contacts')

    return render(request, 'contacts.html', {'CONTACT_EMAIL': settings.DEFAULT_FROM_EMAIL})

def about(request):
    return render(request, 'about.html')

def privacy(request):
    return render(request, 'privacy.html')

def termsOfUse(request):
    return render(request, 'terms-of-use.html')

def paymentPage(request):
    return render(request, 'paymentpage.html')

def _create_checkout(request, name, amount_cents, description):
    """Create a Stripe Checkout session with inline pricing and redirect to it.

    Pricing is defined in code via `price_data`, so no pre-created Stripe
    Products/Prices are needed. The buyer's account is recorded in metadata so
    the webhook can link the resulting Purchase back to the user.
    """
    params = {
        'line_items': [{
            'price_data': {
                'currency': settings.STRIPE_CURRENCY,
                'unit_amount': amount_cents,
                'product_data': {'name': name, 'description': description},
            },
            'quantity': 1,
        }],
        'metadata': {
            'product_name': name,
            'price': f"{amount_cents / 100:.2f}",
            'my_client': request.user.get_username(),
            'user_id': str(request.user.pk),
        },
        'mode': 'payment',
        'success_url': request.build_absolute_uri(reverse('success')),
        'cancel_url': request.build_absolute_uri(reverse('cancel')),
    }
    if request.user.email:
        params['customer_email'] = request.user.email
    try:
        checkout_session = stripe.checkout.Session.create(**params)
    except Exception as e:
        messages.error(request, f"Sorry, we couldn't start checkout: {e}")
        return redirect('pricing')
    return redirect(checkout_session.url, code=303)


@login_required
@require_POST
def checkout_tier2(request):
    """Tier 2: consultation + 1 hour implementation/build."""
    return _create_checkout(
        request, settings.TIER_2_NAME, settings.TIER_2_AMOUNT,
        'Consultation + 1 hour implementation/build',
    )


@login_required
@require_POST
def checkout_tier3(request):
    """Tier 3: consultation + 3 hours implementation/build."""
    return _create_checkout(
        request, settings.TIER_3_NAME, settings.TIER_3_AMOUNT,
        'Consultation + 3 hours implementation/build',
    )

@csrf_exempt
def webhook_view(request):
    payload = request.body

    # A webhook signing secret is required: verifying the Stripe signature is the
    # only way to confirm the event genuinely came from Stripe. Refuse to process
    # unsigned events rather than trusting an unverified payload.
    if not endpoint_secret:
        logger.warning('Webhook secret not configured; refusing to process event.')
        return JsonResponse({'success': False}, status=400)

    sig_header = request.headers.get('stripe-signature')
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError as e:
        # Malformed payload.
        logger.warning('Webhook error while parsing request: %s', e)
        return JsonResponse({'success': False}, status=400)
    except stripe.error.SignatureVerificationError as e:
        logger.warning('Webhook signature verification failed: %s', e)
        return JsonResponse({'success': False}, status=400)

    # Handle the checkout.session.completed event
    if event['type'] == 'checkout.session.completed':
        # Idempotency: Stripe retries delivery of the same event, so skip any
        # event we've already recorded rather than creating a duplicate purchase.
        try:
            event_id = event['id']
        except (KeyError, TypeError):
            event_id = None
        if event_id and Purchase.objects.filter(event_id=event_id).exists():
            return HttpResponse(status=200)

        session = event['data']['object']

        # `session` behaves like a dict on either path; _g reads a key safely.
        def _g(obj, key, default=None):
            try:
                value = obj[key]
            except (KeyError, TypeError):
                return default
            return value if value is not None else default

        details = _g(session, "customer_details", {})
        metadata = _g(session, "metadata", {})

        customer_email = _g(details, "email")
        customer_name = _g(details, "name", "there")
        timestamp = _g(session, "created")
        client_name = _g(metadata, "my_client", customer_email or "guest")
        product_name = _g(metadata, "product_name", "ACE Data")
        price = _g(metadata, "price", "0")

        # Link the purchase to the buyer's account when we know who they are.
        user_id = _g(metadata, "user_id")
        purchaser = CustomUser.objects.filter(pk=user_id).first() if user_id else None

        # Notify the customer of their purchase.
        if customer_email:
            subject = f'Hello {customer_name}!'
            message = f'Thank you for your purchase of our {product_name} service'
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [customer_email],
                fail_silently=True,
            )

        # Record the purchase.
        try:
            Purchase.objects.create(
                event_id=event_id,
                user=purchaser,
                user_name=client_name,
                item_name=product_name,
                amount_paid=price,
                date_of_purchase=date.fromtimestamp(timestamp) if timestamp else None,
                time_of_purchase=(
                    datetime.fromtimestamp(timestamp).strftime("%H:%M:%S")
                    if timestamp else None
                ),
            )
        except IntegrityError:
            # A concurrent retry of the same event recorded it first; ack anyway.
            logger.info('Duplicate webhook event %s ignored.', event_id)

    return HttpResponse(status=200)

def success(request):
    return render(request, 'success.html', {'DEFAULT_FROM_EMAIL': settings.DEFAULT_FROM_EMAIL})

def cancel(request):
    return render(request, 'cancel.html')