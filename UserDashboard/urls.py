# urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('dashboard/stats/', views.api_dashboard_stats, name='dashboard_stats'),
    
    # Wallet
    path('dashboard/wallet/', views.wallet_view, name='wallet'),
    path('dashboard/wallet/fund/', views.fund_wallet_view, name='fund_wallet'),
    
    # Phone Numbers
    path('dashboard/marketplace/', views.phone_marketplace_view, name='marketplace'),
    path('dashboard/numbers/', views.my_numbers_view, name='my_numbers'),
    path('dashboard/numbers/<uuid:number_id>/', views.number_detail_view, name='number_detail'),
    path('dashboard/numbers/<uuid:number_id>/update/', views.update_number_view, name='update_number'),
    path('dashboard/numbers/purchase/<int:phone_number_id>/', views.purchase_number_view, name='purchase_number'),
    
    # SMS
    path('dashboard/sms/inbox/', views.sms_inbox_view, name='sms_inbox'),
    path('dashboard/sms/outbox/', views.sms_outbox_view, name='sms_outbox'),
    path('dashboard/sms/send/', views.send_sms_view, name='send_sms'),
    path('dashboard/sms/api/send/', views.api_send_sms, name='api_send_sms'),
    
    # Calls
    path('dashboard/calls/', views.call_logs_view, name='call_logs'),
    
    # Notifications
    path('dashboard/notifications/', views.notifications_view, name='notifications'),
    path('dashboard/notifications/<uuid:notification_id>/read/', views.mark_notification_read_view, name='mark_notification_read'),
    
    # Referral
    path('dashboard/referral/', views.referral_view, name='referral'),
    
    # Analytics
    path('dashboard/analytics/', views.analytics_view, name='analytics'),
    
    # Settings
    path('dashboard/settings/', views.settings_view, name='settings'),
    path('dashboard/help/', views.help_support_view, name='help'),
    
    # Twilio Webhooks (public endpoints)
    path('webhooks/twilio/sms/', views.twilio_sms_webhook, name='twilio_sms_webhook'),
    path('webhooks/twilio/inbound-sms/', views.twilio_inbound_sms_webhook, name='twilio_inbound_sms_webhook'),
    path('webhooks/twilio/voice/', views.twilio_voice_webhook, name='twilio_voice_webhook'),
    
    # Admin (dropshipping)
    path('admin/dashboard/', views.admin_dashboard_view, name='admin_dashboard'),
    path('admin/users/', views.admin_users_view, name='admin_users'),
    path('admin/transactions/', views.admin_transactions_view, name='admin_transactions'),
]