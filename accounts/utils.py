from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from .models import ActivationToken
from django.utils import timezone
import re

def validate_password(password):
    """Validate password strength"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    
    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one digit"
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character"
    
    return True, "Password is strong"

def validate_email(email):
    """Validate email format"""
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(email_regex, email))

def send_activation_email(user, request):
    """Send activation email to user"""
    # Create activation token
    token = ActivationToken.objects.create(user=user)
    
    # Build activation URL
    if request:
        activation_url = request.build_absolute_uri(f'/activate/{token.token}/')
    else:
        activation_url = f'http://localhost:8000/activate/{token.token}/'
    
    # Email content
    subject = 'Activate Your TiDav Account'
    
    # HTML email template
    html_content = render_to_string('accounts/activation_email.html', {
        'user': user,
        'activation_url': activation_url,
        'activation_code': str(token.token),
    })
    
    # Plain text version
    text_content = strip_tags(html_content)
    
    # Create email
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email]
    )
    
    # Attach HTML version
    email.attach_alternative(html_content, "text/html")
    
    # Send email
    email.send()
    
    return token