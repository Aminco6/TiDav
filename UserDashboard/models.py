from django.db import models
from django.contrib.auth import get_user_model
from decimal import Decimal
import uuid
from datetime import timedelta
from django.utils import timezone

User = get_user_model()

class Wallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    currency = models.CharField(max_length=5, default="USD")
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"{self.user.email} - ${self.balance}"

class WalletTransaction(models.Model):
    TRANSACTION_TYPE = (
        ("fund", "Fund Wallet"),
        ("purchase", "Number Purchase"),
        ("sms", "SMS Charge"),
        ("mms", "MMS Charge"),
        ("call", "Call Charge"),
        ("renewal", "Number Renewal"),
        ("refund", "Refund"),
        ("commission", "Commission"),
        ("withdrawal", "Withdrawal"),
    )
    
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("success", "Success"),
        ("failed", "Failed"),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    tx_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reference = models.CharField(max_length=100, blank=True, null=True, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['tx_type', 'status']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.tx_type} - ${self.amount}"

class AvailablePhoneNumber(models.Model):
    phone_number = models.CharField(max_length=20, unique=True)
    iso_country = models.CharField(max_length=5)
    locality = models.CharField(max_length=50, blank=True, null=True)
    region = models.CharField(max_length=50, blank=True, null=True)
    postal_code = models.CharField(max_length=20, blank=True, null=True)
    
    capabilities = models.JSONField(default=dict)  # Store Twilio capabilities
    supports_sms = models.BooleanField(default=False)
    supports_mms = models.BooleanField(default=False)
    supports_voice = models.BooleanField(default=False)
    supports_fax = models.BooleanField(default=False)
    
    twilio_price = models.DecimalField(max_digits=10, decimal_places=2)
    your_price = models.DecimalField(max_digits=10, decimal_places=2)
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    is_available = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    fetched_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['iso_country', 'locality', 'phone_number']
        indexes = [
            models.Index(fields=['iso_country', 'is_available']),
            models.Index(fields=['your_price']),
        ]
    
    def __str__(self):
        return self.phone_number

class UserPhoneNumber(models.Model):
    STATUS_CHOICES = (
        ("active", "Active"),
        ("suspended", "Suspended"),
        ("cancelled", "Cancelled"),
        ("pending", "Pending"),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='phone_numbers')
    twilio_sid = models.CharField(max_length=50, unique=True)
    phone_number = models.CharField(max_length=20)
    friendly_name = models.CharField(max_length=100, blank=True, null=True)
    iso_country = models.CharField(max_length=5)
    
    capabilities = models.JSONField(default=dict)
    supports_sms = models.BooleanField(default=False)
    supports_mms = models.BooleanField(default=False)
    supports_voice = models.BooleanField(default=False)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2)
    purchased_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    auto_renew = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-purchased_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return self.phone_number
    
    def days_until_expiry(self):
        return (self.expires_at - timezone.now()).days
    
    def is_expired(self):
        return timezone.now() > self.expires_at

class SMSMessage(models.Model):
    DIRECTION_CHOICES = (
        ("inbound", "Inbound"),
        ("outbound", "Outbound"),
    )
    
    STATUS_CHOICES = (
        ("queued", "Queued"),
        ("sent", "Sent"),
        ("delivered", "Delivered"),
        ("undelivered", "Undelivered"),
        ("failed", "Failed"),
        ("received", "Received"),
    )
    
    twilio_sid = models.CharField(max_length=50, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sms_messages')
    phone_number = models.ForeignKey(UserPhoneNumber, on_delete=models.CASCADE, related_name='sms_messages')
    
    sender = models.CharField(max_length=20)
    receiver = models.CharField(max_length=20)
    body = models.TextField()
    
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    segments = models.IntegerField(default=1)
    
    price = models.DecimalField(max_digits=10, decimal_places=4, null=True)
    price_unit = models.CharField(max_length=5, default="USD")
    
    error_code = models.IntegerField(null=True, blank=True)
    error_message = models.CharField(max_length=255, blank=True, null=True)
    
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'direction', 'created_at']),
            models.Index(fields=['phone_number', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.direction} SMS: {self.sender} → {self.receiver}"

class MMSMedia(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(SMSMessage, on_delete=models.CASCADE, related_name='media')
    media_sid = models.CharField(max_length=50)
    content_type = models.CharField(max_length=50)
    media_url = models.URLField(max_length=500)
    file_size = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = "MMS Media"
        indexes = [
            models.Index(fields=['message']),
        ]
    
    def __str__(self):
        return self.media_sid

class CallLog(models.Model):
    DIRECTION_CHOICES = (
        ("inbound", "Inbound"),
        ("outbound", "Outbound"),
    )
    
    STATUS_CHOICES = (
        ("queued", "Queued"),
        ("ringing", "Ringing"),
        ("in-progress", "In Progress"),
        ("completed", "Completed"),
        ("busy", "Busy"),
        ("failed", "Failed"),
        ("no-answer", "No Answer"),
        ("canceled", "Canceled"),
    )
    
    twilio_sid = models.CharField(max_length=50, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='calls')
    phone_number = models.ForeignKey(UserPhoneNumber, on_delete=models.CASCADE, related_name='calls')
    
    from_number = models.CharField(max_length=20)
    to_number = models.CharField(max_length=20)
    
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    
    duration = models.IntegerField(default=0)  # in seconds
    price = models.DecimalField(max_digits=10, decimal_places=4, null=True)
    price_unit = models.CharField(max_length=5, default="USD")
    
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-start_time']
        indexes = [
            models.Index(fields=['user', 'direction', 'start_time']),
        ]
    
    def __str__(self):
        return f"{self.direction} Call: {self.from_number} → {self.to_number}"

class CallRecording(models.Model):
    recording_sid = models.CharField(max_length=50, unique=True)
    call = models.ForeignKey(CallLog, on_delete=models.CASCADE, related_name='recordings')
    duration = models.IntegerField()
    recording_url = models.URLField(max_length=500)
    created_at = models.DateTimeField()
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.recording_sid

class TwilioWebhookLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_sid = models.CharField(max_length=50)
    event_type = models.CharField(max_length=50)
    account_sid = models.CharField(max_length=50, blank=True, null=True)
    payload = models.JSONField()
    processed = models.BooleanField(default=False)
    processing_error = models.TextField(blank=True, null=True)
    received_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-received_at']
        indexes = [
            models.Index(fields=['event_sid']),
            models.Index(fields=['event_type', 'received_at']),
            models.Index(fields=['processed']),
        ]
    
    def __str__(self):
        return f"{self.event_type} - {self.event_sid}"

# Commission model for dropshipping
class Commission(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("paid", "Paid"),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='commissions')
    referral = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='referred_commissions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    percentage = models.DecimalField(max_digits=5, decimal_places=2)
    description = models.CharField(max_length=255)
    reference = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['referral']),
        ]
    
    def __str__(self):
        return f"Commission: {self.user.email} - ${self.amount}"

# Referral system
class Referral(models.Model):
    referrer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='referrals_made')
    referred = models.OneToOneField(User, on_delete=models.CASCADE, related_name='referred_by')
    code = models.CharField(max_length=20, unique=True)
    commission_earned = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['referrer', 'referred']
    
    def __str__(self):
        return f"{self.referrer.email} → {self.referred.email}"

# Notification model
class Notification(models.Model):
    TYPE_CHOICES = (
        ("info", "Information"),
        ("success", "Success"),
        ("warning", "Warning"),
        ("error", "Error"),
        ("payment", "Payment"),
        ("sms", "SMS"),
        ("call", "Call"),
        ("number", "Number"),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    action_url = models.URLField(max_length=500, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.email}: {self.title}"