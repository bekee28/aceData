from django.urls import path
from django.views.generic import RedirectView
from . import views
#from django.contrib.auth.views import LoginView
from .views import ResetPasswordView
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.home, name='home'),
    # `/home/` is kept as a permanent redirect to the canonical home URL so old
    # links keep working without duplicating the route or the `home` name.
    path('home/', RedirectView.as_view(pattern_name='home', permanent=True)),
    path('signup/', views.sign_up, name='signup'),
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('account/', views.account_page, name='account'),
    path('pricing/', views.pricing, name='pricing'),
    path('services/', views.services, name='services'),
    path('contacts/', views.contacts, name='contacts'),
    path('about/', views.about, name='about'),
    path('privacy/', views.privacy, name='privacy'),
    path('terms-of-use/', views.termsOfUse, name='terms-of-use'),
    path('change-password/', views.change_password, name='change_password'),

    path('password_reset/', ResetPasswordView.as_view(), name='password_reset_custom'),

    path('password_reset_sent/', views.reset_sent, name='password_reset_sent'),

    path('password_reset_confirm/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(template_name='password_reset_conf.html'),
         name='password_reset_conf'),

    path('reset/done/', 
        auth_views.PasswordResetCompleteView.as_view(template_name = "password_reset_done.html"), 
        name ='password_reset_done'),
    #seems the first argument in the path func need to be the same as that of the default path url provided by django

    path('paymentpage/', views.paymentPage, name='checkout'),
    path('checkout/build/', views.checkout_tier2, name='tier2'),       # consultation + 1 hour
    path('checkout/build-pro/', views.checkout_tier3, name='tier3'),   # consultation + 3 hours
    path('success/', views.success, name='success'),
    path('cancel/', views.cancel, name='cancel'),
    path('webhook/', views.webhook_view, name='webhook'),
]

# Add the staticfiles_urlpatterns to serve static files during development.
# urlpatterns += staticfiles_urlpatterns()

