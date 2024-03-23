from django.urls import path
from . import views
#from django.contrib.auth.views import LoginView
from .views import ResetPasswordView
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.home, name='home'),
    path('home/', views.home, name='home'),
    path('signup/', views.sign_up, name='signup'),
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('account/', views.account_page, name='account'),
    path('pricing/', views.pricing, name='pricing'),
    path('services/', views.services, name='services'),
    path('hire-us/', views.hireUs, name='hire-us'),
    path('help-center/', views.helpCenter, name='help-center'),
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
    path('checkoutT1/', views.checkoutT1, name='tier1'), #'checkoutT1' has to be the same as that in the view, name={name on the payment.html action tag} because action tag points to the name on the url pattern'
    path('checkoutT2/', views.checkoutT2, name='tier2'),
    path('success/', views.success, name='success'),
    path('cancel/', views.cancel, name='cancel'),
    path('webhook/', views.webhook_view, name='webhook'),
]

# Add the staticfiles_urlpatterns to serve static files during development.
# urlpatterns += staticfiles_urlpatterns()

