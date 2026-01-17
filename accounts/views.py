from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.hashers import make_password
import json
from django.http import JsonResponse
from .models import User, UserProfile, ActivationToken
from .utils import validate_password, validate_email, send_activation_email
import re

from django.contrib.auth.decorators import login_required

from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string





#@login_required(login_url='/login/')
def index(request):
  return render(request, 'accounts/index.html')


def send_activation_email(user, request):
    """Send activation email to user"""
    try:
        # Create activation token
        token = ActivationToken.objects.create(user=user)
        
        # Build activation URL
        if request:
            activation_url = request.build_absolute_uri(f'/activate/?email={user.email}')
        else:
            activation_url = f'http://localhost:8000/activate/?email={user.email}'
        
        # Email content
        subject = '🎉 Activate Your TiDav Account - Your Activation Code Inside'
        
        # HTML email template
        html_content = render_to_string('accounts/activation_email.html', {
            'user': user,
            'activation_url': activation_url,
            'activation_code': str(token.token),
        })
        
        # Plain text version (fallback)
        text_content = f"""
        Welcome to TiDav, {user.first_name}!
        
        Your Activation Code: {token.token}
        
        To activate your account:
        1. Go to: {activation_url}
        2. Enter this code: {token.token}
        3. Click "Activate Account"
        
        This code expires in 7 days.
        
        If you didn't create a TiDav account, please ignore this email.
        
        ---
        TiDav Premium Numbers
        """
        
        # Create email
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email='TiDav <noreply@tidav.com>',
            to=[user.email],
            reply_to=['support@tidav.com']
        )
        
        # Attach HTML version
        email.attach_alternative(html_content, "text/html")
        email.content_subtype = "html"
        
        # Send email
        email.send()
        
        print(f"✅ Activation email sent to {user.email}")
        print(f"📧 Activation code: {token.token}")
        print(f"🔗 Activation URL: {activation_url}")
        
        return token
        
    except Exception as e:
        print(f"❌ Error sending activation email: {str(e)}")
        # Still create token even if email fails
        token = ActivationToken.objects.create(user=user)
        return token






@csrf_exempt
def signup_view(request):
    if request.method == 'POST':
        try:
            # Parse JSON data
            data = json.loads(request.body)
            
            # Extract form data
            first_name = data.get('firstName', '').strip()
            last_name = data.get('lastName', '').strip()
            email = data.get('email', '').strip().lower()
            phone = data.get('phone', '').strip()
            country_code = data.get('countryCode', '').strip()
            country = data.get('country', '').strip()
            password = data.get('password', '')
            confirm_password = data.get('confirmPassword', '')
            
            # Validation
            errors = {}
            
            # Name validation
            if not first_name:
                errors['firstName'] = ['First name is required']
            elif len(first_name) < 2:
                errors['firstName'] = ['First name must be at least 2 characters']
            
            if not last_name:
                errors['lastName'] = ['Last name is required']
            elif len(last_name) < 2:
                errors['lastName'] = ['Last name must be at least 2 characters']
            
            # Email validation
            if not email:
                errors['email'] = ['Email is required']
            elif not validate_email(email):
                errors['email'] = ['Please enter a valid email address']
            elif User.objects.filter(email=email).exists():
                errors['email'] = ['This email is already registered']
            
            # Phone validation
            if not phone:
                errors['phone'] = ['Phone number is required']
            elif not re.match(r'^[\d\s\-\+\(\)]{8,20}$', phone):
                errors['phone'] = ['Please enter a valid phone number']
            
            # Country validation
            if not country:
                errors['country'] = ['Please select your country']
            
            # Password validation
            if not password:
                errors['password'] = ['Password is required']
            else:
                is_valid, password_error = validate_password(password)
                if not is_valid:
                    errors['password'] = [password_error]
            
            # Confirm password
            if password != confirm_password:
                errors['confirmPassword'] = ['Passwords do not match']
            
            # Return errors if any
            if errors:
                return JsonResponse({
                    'success': False,
                    'errors': errors
                })
            
            # Create user
            try:
                user = User.objects.create(
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    password=make_password(password),
                    is_active=False
                )
                
                # Create user profile
                UserProfile.objects.create(
                    user=user,
                    phone_number=phone,
                    country_code=country_code,
                    country=country
                )
                
                # Send activation email
                try:
                    token = send_activation_email(user, request)
                    
                    # Print to console for debugging
                    print("\n" + "="*60)
                    print("🎉 USER REGISTERED SUCCESSFULLY")
                    print("="*60)
                    print(f"👤 Name: {first_name} {last_name}")
                    print(f"📧 Email: {email}")
                    print(f"📱 Phone: {phone}")
                    print(f"🌍 Country: {country}")
                    print(f"🔑 Activation Code: {token.token}")
                    print(f"🔗 Activation URL: /activate/?email={email}")
                    print("="*60 + "\n")
                    
                    return JsonResponse({
                        'success': True,
                        'message': 'Registration successful! Check your email for the activation code.',
                        'redirect_url': f'/activate/?email={email}',
                        'activation_sent': True,
                        'debug_info': {
                            'email': email,
                            'code': token.token
                        }
                    })
                    
                except Exception as email_error:
                    print(f"❌ Email error: {str(email_error)}")
                    # Create token even if email fails
                    token = ActivationToken.objects.create(user=user)
                    return JsonResponse({
                        'success': True,
                        'message': f'Account created! But email failed. Your code: {token.token}',
                        'redirect_url': f'/activate/?email={email}',
                        'activation_sent': False,
                        'debug_code': token.token
                    })
                
            except Exception as e:
                print(f"❌ User creation error: {str(e)}")
                return JsonResponse({
                    'success': False,
                    'errors': {'__all__': [f'Error creating account: {str(e)}']}
                })
                
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'errors': {'__all__': ['Invalid data format']}
            })
    
    # GET request - render signup page
    return render(request, 'accounts/signup.html')







from django.contrib.auth import login as auth_login  # Rename to avoid conflict

def activation_view(request, token=None):
    email = request.GET.get('email', '')
    
    if request.method == 'POST':
        activation_code = request.POST.get('activation_code', '').strip().upper()
        
        # Clean the code
        clean_code = activation_code.replace(' ', '').replace('-', '').upper()
        
        print(f"🔍 Activation attempt for code: {clean_code}")
        
        if not clean_code:
            messages.error(request, 'Please enter an activation code.')
        elif len(clean_code) != 12:
            messages.error(request, 'Activation code must be 12 characters.')
        else:
            try:
                # Find the activation token
                activation_token = ActivationToken.objects.get(
                    clean_token=clean_code,
                    is_used=False
                )
                
                # Check expiration
                if timezone.now() > activation_token.expires_at:
                    messages.error(request, 'Activation code has expired.')
                    return render(request, 'accounts/activation.html', {
                        'email': activation_token.user.email
                    })
                
                # Activate user
                user = activation_token.user
                user.is_active = True
                user.save()
                
                # Mark token as used
                activation_token.is_used = True
                activation_token.save()
                
                # Auto login - Use Django's auth_login function
                auth_login(request, user)
                
                print(f"✅ Successfully activated and logged in: {user.email}")
                return redirect('activation_success')
                
            except ActivationToken.DoesNotExist:
                # Check if it was used
                if ActivationToken.objects.filter(clean_token=clean_code, is_used=True).exists():
                    messages.error(request, 'This code has already been used.')
                else:
                    messages.error(request, 'Invalid activation code.')
            except Exception as e:
                print(f"❌ Error: {str(e)}")
                import traceback
                traceback.print_exc()
                messages.error(request, 'An error occurred.')
    
    return render(request, 'accounts/activation.html', {'email': email})
    

@csrf_exempt
def resend_activation_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = data.get('email', '').strip().lower()
            
            if not email:
                return JsonResponse({
                    'success': False,
                    'message': 'Email is required'
                })
            
            try:
                user = User.objects.get(email=email)
                
                # Check if user is already active
                if user.is_active:
                    return JsonResponse({
                        'success': False,
                        'message': 'Account is already activated. Please login.'
                    })
                
                # Check if there's a valid unused token
                existing_token = ActivationToken.objects.filter(
                    user=user,
                    is_used=False,
                    expires_at__gt=timezone.now()
                ).first()
                
                if existing_token:
                    # Resend the existing token
                    send_activation_email(user, request)
                    return JsonResponse({
                        'success': True,
                        'message': 'Activation email resent! Please check your inbox.',
                        'resent': True,
                        'code': existing_token.token
                    })
                else:
                    # Create new token
                    ActivationToken.objects.filter(user=user, is_used=False).update(is_used=True)
                    new_token = ActivationToken.objects.create(user=user)
                    send_activation_email(user, request)
                    return JsonResponse({
                        'success': True,
                        'message': 'New activation email sent! Please check your inbox.',
                        'resent': True,
                        'new_code': new_token.token
                    })
                
            except User.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'No account found with this email. Please sign up first.'
                })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid request format'
            })
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method'
    })
    
from django.views.decorators.csrf import csrf_exempt
import json
from django.http import JsonResponse
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from .models import User, UserProfile, ActivationToken
import re

@csrf_exempt
def login_view(request):
    """Handle email/password login"""
    if request.method == 'POST':
        try:
            # Parse JSON data
            data = json.loads(request.body)
            
            email = data.get('email', '').strip().lower()
            password = data.get('password', '')
            remember_me = data.get('remember', False)
            
            # Validation
            errors = {}
            
            if not email:
                errors['email'] = ['Email is required']
            elif not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
                errors['email'] = ['Please enter a valid email address']
            
            if not password:
                errors['password'] = ['Password is required']
            
            if errors:
                return JsonResponse({
                    'success': False,
                    'errors': errors
                })
            
            try:
                # Get user by email
                user = User.objects.get(email=email)
                
                # Check if account is active
                if not user.is_active:
                    # Check if there's an activation token
                    token = ActivationToken.objects.filter(user=user, is_used=False).first()
                    if token:
                        return JsonResponse({
                            'success': False,
                            'errors': {
                                '__all__': [
                                    'Account not activated. Please check your email for activation code.',
                                    f'Your activation code: {token.token}'
                                ]
                            },
                            'needs_activation': True,
                            'email': email
                        })
                    else:
                        return JsonResponse({
                            'success': False,
                            'errors': {
                                '__all__': ['Account not activated. Please contact support.']
                            }
                        })
                
                # Check password
                if user.check_password(password):
                    # Login successful
                    auth_login(request, user)
                    
                    # Set session expiry based on remember me
                    if remember_me:
                        request.session.set_expiry(1209600)  # 2 weeks
                    else:
                        request.session.set_expiry(0)  # Browser session
                    
                    return JsonResponse({
                        'success': True,
                        'message': 'Login successful!',
                        'redirect_url': '/dashboard/'  # Change to your dashboard URL
                    })
                else:
                    return JsonResponse({
                        'success': False,
                        'errors': {
                            'password': ['Invalid password.']
                        }
                    })
                    
            except User.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'errors': {
                        'email': ['No account found with this email.']
                    }
                })
                
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'errors': {'__all__': ['Invalid data format']}
            })
    
    # GET request - render login page
    return render(request, 'accounts/login.html')

@csrf_exempt
def google_login_view(request):
    """Handle Google OAuth login/signup"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            action = data.get('action')
            
            if action == 'google_auth':
                # In production, you would:
                # 1. Verify the Google token
                # 2. Get user info from Google
                # 3. Create or authenticate user
                
                # For demo purposes, we'll simulate Google authentication
                google_token = data.get('token')
                google_email = data.get('email', 'demo@google.com')
                google_name = data.get('name', 'Google User')
                
                print(f"🔐 Google login attempt for: {google_email}")
                
                try:
                    # Check if user exists
                    user = User.objects.get(email=google_email)
                    
                    # Check if user is active
                    if not user.is_active:
                        user.is_active = True
                        user.save()
                    
                    # Login the user
                    auth_login(request, user)
                    
                    return JsonResponse({
                        'success': True,
                        'message': 'Google login successful!',
                        'redirect_url': '/dashboard/',
                        'user': {
                            'email': user.email,
                            'name': user.get_full_name()
                        }
                    })
                    
                except User.DoesNotExist:
                    # Create new user from Google
                    # Extract first and last name
                    name_parts = google_name.split(' ', 1)
                    first_name = name_parts[0] if len(name_parts) > 0 else 'Google'
                    last_name = name_parts[1] if len(name_parts) > 1 else 'User'
                    
                    # Create user with random password (won't be used for Google login)
                    import random
                    import string
                    random_password = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(20))
                    
                    user = User.objects.create(
                        email=google_email,
                        first_name=first_name,
                        last_name=last_name,
                        username=google_email,
                        password=make_password(random_password),
                        is_active=True  # Google accounts are auto-activated
                    )
                    
                    # Create user profile
                    UserProfile.objects.create(
                        user=user,
                        google_auth=True,
                        google_id=data.get('google_id', 'demo_google_id')
                    )
                    
                    # Login the user
                    auth_login(request, user)
                    
                    return JsonResponse({
                        'success': True,
                        'message': 'Account created with Google! Welcome!',
                        'redirect_url': '/dashboard/',
                        'user': {
                            'email': user.email,
                            'name': user.get_full_name()
                        }
                    })
                    
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid action'
                })
                
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid data format'
            })
        except Exception as e:
            print(f"❌ Google login error: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': f'Error: {str(e)}'
            })
    
    # GET request - redirect to Google OAuth
    # In production, this would redirect to Google's OAuth URL
    return JsonResponse({
        'success': False,
        'message': 'Use POST method for Google login'
    })

def logout_view(request):
    """Handle user logout"""
    if request.user.is_authenticated:
        auth_logout(request)
        messages.success(request, 'You have been logged out successfully.')
    
    return redirect('login')

@login_required
def dashboard_view(request):
    """Dashboard view after login"""
    return render(request, 'accounts/dashboard.html', {
        'user': request.user
    })
    
    
    
    
    
    
    
    
    



def activation_success_view(request):
    return render(request, 'accounts/activation_success.html')



def check_email_view(request):
    """Check if email exists"""
    if request.method == 'GET':
        email = request.GET.get('email', '').strip().lower()
        
        if not email:
            return JsonResponse({'exists': False})
        
        exists = User.objects.filter(email=email).exists()
        return JsonResponse({'exists': exists})
    
    return JsonResponse({'exists': False})

def check_password_strength_view(request):
    """Check password strength via API"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            password = data.get('password', '')
            
            if not password:
                return JsonResponse({
                    'valid': False,
                    'strength': 0,
                    'message': 'Password is empty'
                })
            
            is_valid, message = validate_password(password)
            
            # Calculate strength percentage
            strength = 0
            if len(password) >= 8:
                strength += 20
            if re.search(r'[A-Z]', password):
                strength += 20
            if re.search(r'[a-z]', password):
                strength += 20
            if re.search(r'[0-9]', password):
                strength += 20
            if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
                strength += 20
            
            return JsonResponse({
                'valid': is_valid,
                'strength': strength,
                'message': message
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'valid': False,
                'strength': 0,
                'message': 'Invalid request'
            })
    
    return JsonResponse({
        'valid': False,
        'strength': 0,
        'message': 'Invalid method'
    })
    
    
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required

@login_required
def logout_view(request):
    auth_logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('login')    
    