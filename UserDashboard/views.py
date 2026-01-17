# views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.db.models import Sum, Count, Q, F, DecimalField
from django.db.models.functions import TruncMonth, TruncDay
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta
import json
import uuid
from decimal import Decimal
from .models import (
    Wallet, WalletTransaction, AvailablePhoneNumber, UserPhoneNumber,
    SMSMessage, MMSMedia, CallLog, CallRecording, TwilioWebhookLog,
    Commission, Referral, Notification
)
from django.contrib.auth import get_user_model

User = get_user_model()

# ==================== DASHBOARD VIEWS ====================

@login_required
def dashboard_view(request):
    """Main dashboard view"""
    user = request.user
    
    # Get wallet balance
    wallet = user.wallet
    
    # Get stats
    stats = {
        'phone_numbers': user.phone_numbers.filter(status='active').count(),
        'total_sms': user.sms_messages.count(),
        'total_calls': user.calls.count(),
        'unread_notifications': user.notifications.filter(is_read=False).count(),
    }
    
    # Recent transactions
    recent_transactions = user.transactions.all().order_by('-created_at')[:10]
    
    # Recent SMS
    recent_sms = user.sms_messages.all().order_by('-created_at')[:5]
    
    # Expiring numbers
    expiring_numbers = user.phone_numbers.filter(
        expires_at__lt=timezone.now() + timedelta(days=7),
        status='active'
    ).order_by('expires_at')[:5]
    
    context = {
        'wallet': wallet,
        'stats': stats,
        'recent_transactions': recent_transactions,
        'recent_sms': recent_sms,
        'expiring_numbers': expiring_numbers,
    }
    
    return render(request, 'user_dashboard/dashboard.html', context)

@login_required
def wallet_view(request):
    """Wallet management view"""
    user = request.user
    wallet = user.wallet
    
    # Filter transactions
    transaction_type = request.GET.get('type', 'all')
    status_filter = request.GET.get('status', 'all')
    
    transactions = user.transactions.all()
    
    if transaction_type != 'all':
        transactions = transactions.filter(tx_type=transaction_type)
    
    if status_filter != 'all':
        transactions = transactions.filter(status=status_filter)
    
    # Pagination
    paginator = Paginator(transactions.order_by('-created_at'), 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'wallet': wallet,
        'page_obj': page_obj,
        'transaction_types': WalletTransaction.TRANSACTION_TYPE,
        'selected_type': transaction_type,
        'selected_status': status_filter,
    }
    
    return render(request, 'user_dashboard/wallet.html', context)

@login_required
def fund_wallet_view(request):
    """Fund wallet view"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            amount = Decimal(data.get('amount', 0))
            payment_method = data.get('payment_method', 'stripe')
            
            if amount <= 0:
                return JsonResponse({
                    'success': False,
                    'error': 'Amount must be greater than 0'
                })
            
            # Generate unique reference
            reference = f"FUND-{uuid.uuid4().hex[:12].upper()}"
            
            # Create pending transaction
            transaction = WalletTransaction.objects.create(
                user=request.user,
                tx_type='fund',
                amount=amount,
                reference=reference,
                status='pending',
                metadata={
                    'payment_method': payment_method,
                    'processed_at': None,
                }
            )
            
            # In production, you would integrate with payment gateway here
            # For demo, auto-approve after 2 seconds
            return JsonResponse({
                'success': True,
                'message': 'Payment initiated',
                'transaction_id': str(transaction.id),
                'reference': reference,
                'amount': str(amount),
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid data format'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return render(request, 'user_dashboard/fund_wallet.html')

# ==================== PHONE NUMBER MARKETPLACE ====================

@login_required
def phone_marketplace_view(request):
    """Browse available phone numbers"""
    # Get filters
    country = request.GET.get('country', '')
    locality = request.GET.get('locality', '')
    supports_sms = request.GET.get('supports_sms', '')
    supports_voice = request.GET.get('supports_voice', '')
    price_min = request.GET.get('price_min', '')
    price_max = request.GET.get('price_max', '')
    sort_by = request.GET.get('sort_by', 'price_asc')
    
    # Start with all available numbers
    numbers = AvailablePhoneNumber.objects.filter(is_available=True)
    
    # Apply filters
    if country:
        numbers = numbers.filter(iso_country=country)
    
    if locality:
        numbers = numbers.filter(locality__icontains=locality)
    
    if supports_sms == 'true':
        numbers = numbers.filter(supports_sms=True)
    
    if supports_voice == 'true':
        numbers = numbers.filter(supports_voice=True)
    
    if price_min:
        numbers = numbers.filter(your_price__gte=Decimal(price_min))
    
    if price_max:
        numbers = numbers.filter(your_price__lte=Decimal(price_max))
    
    # Apply sorting
    if sort_by == 'price_asc':
        numbers = numbers.order_by('your_price')
    elif sort_by == 'price_desc':
        numbers = numbers.order_by('-your_price')
    elif sort_by == 'country':
        numbers = numbers.order_by('iso_country', 'locality')
    elif sort_by == 'featured':
        numbers = numbers.order_by('-is_featured', 'your_price')
    
    # Get unique countries for filter dropdown
    countries = AvailablePhoneNumber.objects.filter(is_available=True).values_list(
        'iso_country', flat=True
    ).distinct().order_by('iso_country')
    
    # Get unique localities for filter dropdown
    localities = AvailablePhoneNumber.objects.filter(
        is_available=True, locality__isnull=False
    ).values_list('locality', flat=True).distinct().order_by('locality')
    
    # Pagination
    paginator = Paginator(numbers, 24)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'countries': countries,
        'localities': localities,
        'filters': {
            'country': country,
            'locality': locality,
            'supports_sms': supports_sms,
            'supports_voice': supports_voice,
            'price_min': price_min,
            'price_max': price_max,
            'sort_by': sort_by,
        }
    }
    
    return render(request, 'user_dashboard/marketplace.html', context)

@login_required
def purchase_number_view(request, phone_number_id):
    """Purchase a phone number"""
    if request.method == 'POST':
        try:
            number = get_object_or_404(AvailablePhoneNumber, id=phone_number_id, is_available=True)
            
            # Check wallet balance
            wallet = request.user.wallet
            if wallet.balance < number.your_price:
                return JsonResponse({
                    'success': False,
                    'error': 'Insufficient balance'
                })
            
            # Generate Twilio SID (in production, this would be from Twilio API)
            twilio_sid = f"PN{uuid.uuid4().hex[:32].upper()}"
            
            # Create user phone number
            user_number = UserPhoneNumber.objects.create(
                user=request.user,
                twilio_sid=twilio_sid,
                phone_number=number.phone_number,
                iso_country=number.iso_country,
                supports_sms=number.supports_sms,
                supports_mms=number.supports_mms,
                supports_voice=number.supports_voice,
                capabilities=number.capabilities,
                monthly_price=number.monthly_price,
                expires_at=timezone.now() + timedelta(days=30)
            )
            
            # Mark as unavailable
            number.is_available = False
            number.save()
            
            # Create transaction
            transaction = WalletTransaction.objects.create(
                user=request.user,
                tx_type='purchase',
                amount=number.your_price,
                reference=f"PURCHASE-{uuid.uuid4().hex[:8].upper()}",
                status='success',
                metadata={
                    'phone_number': number.phone_number,
                    'twilio_sid': twilio_sid,
                }
            )
            
            # Create notification
            Notification.objects.create(
                user=request.user,
                notification_type='success',
                title='Phone Number Purchased',
                message=f'You have successfully purchased {number.phone_number}',
                action_url=f'/dashboard/numbers/{user_number.id}/'
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Number purchased successfully',
                'number_id': str(user_number.id),
                'phone_number': number.phone_number,
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({
        'success': False,
        'error': 'Invalid request method'
    })

# ==================== MY NUMBERS ====================

@login_required
def my_numbers_view(request):
    """View user's purchased numbers"""
    numbers = request.user.phone_numbers.all().order_by('-purchased_at')
    
    # Filters
    status_filter = request.GET.get('status', 'all')
    if status_filter != 'all':
        numbers = numbers.filter(status=status_filter)
    
    # Search
    search_query = request.GET.get('search', '')
    if search_query:
        numbers = numbers.filter(
            Q(phone_number__icontains=search_query) |
            Q(friendly_name__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(numbers, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'search_query': search_query,
    }
    
    return render(request, 'user_dashboard/my_numbers.html', context)

@login_required
def number_detail_view(request, number_id):
    """Detail view for a specific number"""
    number = get_object_or_404(UserPhoneNumber, id=number_id, user=request.user)
    
    # Get recent SMS
    recent_sms = number.sms_messages.all().order_by('-created_at')[:10]
    
    # Get recent calls
    recent_calls = number.calls.all().order_by('-start_time')[:10]
    
    # Get usage stats
    sms_stats = number.sms_messages.aggregate(
        total=Count('id'),
        inbound=Count('id', filter=Q(direction='inbound')),
        outbound=Count('id', filter=Q(direction='outbound')),
    )
    
    call_stats = number.calls.aggregate(
        total=Count('id'),
        inbound=Count('id', filter=Q(direction='inbound')),
        outbound=Count('id', filter=Q(direction='outbound')),
        total_duration=Sum('duration'),
    )
    
    context = {
        'number': number,
        'recent_sms': recent_sms,
        'recent_calls': recent_calls,
        'sms_stats': sms_stats,
        'call_stats': call_stats,
    }
    
    return render(request, 'user_dashboard/number_detail.html', context)

@login_required
def update_number_view(request, number_id):
    """Update number settings"""
    if request.method == 'POST':
        try:
            number = get_object_or_404(UserPhoneNumber, id=number_id, user=request.user)
            data = json.loads(request.body)
            
            # Update fields
            if 'friendly_name' in data:
                number.friendly_name = data['friendly_name']
            
            if 'auto_renew' in data:
                number.auto_renew = data['auto_renew'] == 'true'
            
            if 'status' in data and data['status'] in ['active', 'suspended']:
                number.status = data['status']
            
            number.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Number updated successfully'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid data format'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({
        'success': False,
        'error': 'Invalid request method'
    })

# ==================== SMS MANAGEMENT ====================

@login_required
def sms_inbox_view(request):
    """SMS inbox view"""
    # Get user's numbers
    user_numbers = request.user.phone_numbers.filter(status='active')
    
    # Get SMS messages
    sms_messages = SMSMessage.objects.filter(
        user=request.user,
        direction='inbound'
    ).order_by('-created_at')
    
    # Filter by number
    number_filter = request.GET.get('number', 'all')
    if number_filter != 'all':
        sms_messages = sms_messages.filter(phone_number_id=number_filter)
    
    # Filter by status
    status_filter = request.GET.get('status', 'all')
    if status_filter != 'all':
        sms_messages = sms_messages.filter(status=status_filter)
    
    # Search
    search_query = request.GET.get('search', '')
    if search_query:
        sms_messages = sms_messages.filter(
            Q(body__icontains=search_query) |
            Q(sender__icontains=search_query) |
            Q(receiver__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(sms_messages, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'user_numbers': user_numbers,
        'filters': {
            'number': number_filter,
            'status': status_filter,
            'search': search_query,
        }
    }
    
    return render(request, 'user_dashboard/sms_inbox.html', context)

@login_required
def sms_outbox_view(request):
    """SMS outbox view"""
    # Get user's numbers
    user_numbers = request.user.phone_numbers.filter(status='active')
    
    # Get SMS messages
    sms_messages = SMSMessage.objects.filter(
        user=request.user,
        direction='outbound'
    ).order_by('-created_at')
    
    # Filters (same as inbox)
    number_filter = request.GET.get('number', 'all')
    status_filter = request.GET.get('status', 'all')
    search_query = request.GET.get('search', '')
    
    if number_filter != 'all':
        sms_messages = sms_messages.filter(phone_number_id=number_filter)
    
    if status_filter != 'all':
        sms_messages = sms_messages.filter(status=status_filter)
    
    if search_query:
        sms_messages = sms_messages.filter(
            Q(body__icontains=search_query) |
            Q(sender__icontains=search_query) |
            Q(receiver__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(sms_messages, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'user_numbers': user_numbers,
        'filters': {
            'number': number_filter,
            'status': status_filter,
            'search': search_query,
        }
    }
    
    return render(request, 'user_dashboard/sms_outbox.html', context)

@login_required
def send_sms_view(request):
    """Send SMS view"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Validate data
            phone_number_id = data.get('phone_number_id')
            to_number = data.get('to_number')
            message = data.get('message')
            
            if not all([phone_number_id, to_number, message]):
                return JsonResponse({
                    'success': False,
                    'error': 'Missing required fields'
                })
            
            # Get phone number
            phone_number = get_object_or_404(
                UserPhoneNumber, 
                id=phone_number_id, 
                user=request.user,
                status='active',
                supports_sms=True
            )
            
            # Check wallet balance (assume $0.01 per SMS segment)
            segments = (len(message) // 160) + 1
            sms_cost = Decimal('0.01') * segments
            
            wallet = request.user.wallet
            if wallet.balance < sms_cost:
                return JsonResponse({
                    'success': False,
                    'error': 'Insufficient balance'
                })
            
            # Generate Twilio SID
            twilio_sid = f"SM{uuid.uuid4().hex[:32].upper()}"
            
            # Create SMS record
            sms = SMSMessage.objects.create(
                twilio_sid=twilio_sid,
                user=request.user,
                phone_number=phone_number,
                sender=phone_number.phone_number,
                receiver=to_number,
                body=message,
                direction='outbound',
                status='queued',
                segments=segments,
                price=sms_cost,
                created_at=timezone.now()
            )
            
            # Create transaction
            transaction = WalletTransaction.objects.create(
                user=request.user,
                tx_type='sms',
                amount=sms_cost,
                reference=f"SMS-{uuid.uuid4().hex[:8].upper()}",
                status='success',
                metadata={
                    'sms_id': str(sms.id),
                    'to_number': to_number,
                    'segments': segments,
                }
            )
            
            # In production, this would call Twilio API
            # For demo, simulate sending
            import time
            time.sleep(1)
            
            # Update SMS status
            sms.status = 'sent'
            sms.save()
            
            return JsonResponse({
                'success': True,
                'message': 'SMS sent successfully',
                'sms_id': str(sms.id),
                'cost': str(sms_cost),
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid data format'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    # GET request - show form
    user_numbers = request.user.phone_numbers.filter(
        status='active', 
        supports_sms=True
    ).order_by('phone_number')
    
    context = {
        'user_numbers': user_numbers,
    }
    
    return render(request, 'user_dashboard/send_sms.html', context)

# ==================== CALL MANAGEMENT ====================

@login_required
def call_logs_view(request):
    """Call logs view"""
    # Get call logs
    call_logs = CallLog.objects.filter(user=request.user).order_by('-start_time')
    
    # Filter by number
    number_filter = request.GET.get('number', 'all')
    if number_filter != 'all':
        call_logs = call_logs.filter(phone_number_id=number_filter)
    
    # Filter by direction
    direction_filter = request.GET.get('direction', 'all')
    if direction_filter != 'all':
        call_logs = call_logs.filter(direction=direction_filter)
    
    # Filter by status
    status_filter = request.GET.get('status', 'all')
    if status_filter != 'all':
        call_logs = call_logs.filter(status=status_filter)
    
    # Search
    search_query = request.GET.get('search', '')
    if search_query:
        call_logs = call_logs.filter(
            Q(from_number__icontains=search_query) |
            Q(to_number__icontains=search_query)
        )
    
    # Get user numbers for filter
    user_numbers = request.user.phone_numbers.filter(status='active')
    
    # Pagination
    paginator = Paginator(call_logs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'user_numbers': user_numbers,
        'filters': {
            'number': number_filter,
            'direction': direction_filter,
            'status': status_filter,
            'search': search_query,
        }
    }
    
    return render(request, 'user_dashboard/call_logs.html', context)

# ==================== NOTIFICATIONS ====================

@login_required
def notifications_view(request):
    """Notifications view"""
    notifications = request.user.notifications.all().order_by('-created_at')
    
    # Filter by read status
    read_filter = request.GET.get('read', 'all')
    if read_filter == 'unread':
        notifications = notifications.filter(is_read=False)
    elif read_filter == 'read':
        notifications = notifications.filter(is_read=True)
    
    # Filter by type
    type_filter = request.GET.get('type', 'all')
    if type_filter != 'all':
        notifications = notifications.filter(notification_type=type_filter)
    
    # Mark all as read
    if request.GET.get('mark_all_read') == 'true':
        notifications.update(is_read=True)
        messages.success(request, 'All notifications marked as read')
        return redirect('notifications')
    
    # Pagination
    paginator = Paginator(notifications, 30)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'read_filter': read_filter,
        'type_filter': type_filter,
    }
    
    return render(request, 'user_dashboard/notifications.html', context)

@login_required
def mark_notification_read_view(request, notification_id):
    """Mark notification as read"""
    if request.method == 'POST':
        notification = get_object_or_404(
            Notification, 
            id=notification_id, 
            user=request.user
        )
        notification.is_read = True
        notification.save()
        
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False})

# ==================== REFERRAL SYSTEM ====================

@login_required
def referral_view(request):
    """Referral dashboard"""
    user = request.user
    
    # Get referral info
    try:
        referral = user.referred_by
    except Referral.DoesNotExist:
        # Create referral if doesn't exist
        import random
        import string
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        referral = Referral.objects.create(
            referrer=user,
            referred=user,
            code=code
        )
    
    # Get referral stats
    referred_users = Referral.objects.filter(referrer=user).exclude(referred=user)
    
    # Get commission stats
    commissions = user.commissions.filter(status='approved').aggregate(
        total=Sum('amount'),
        count=Count('id')
    )
    
    # Get recent referrals
    recent_referrals = referred_users.select_related('referred').order_by('-created_at')[:10]
    
    # Get recent commissions
    recent_commissions = user.commissions.all().order_by('-created_at')[:10]
    
    context = {
        'referral': referral,
        'referred_users': referred_users,
        'referred_count': referred_users.count(),
        'commission_total': commissions['total'] or Decimal('0.00'),
        'commission_count': commissions['count'] or 0,
        'recent_referrals': recent_referrals,
        'recent_commissions': recent_commissions,
    }
    
    return render(request, 'user_dashboard/referral.html', context)

# ==================== ANALYTICS ====================

@login_required
def analytics_view(request):
    """Analytics dashboard"""
    user = request.user
    
    # Time range
    time_range = request.GET.get('range', '30d')
    
    if time_range == '7d':
        days = 7
    elif time_range == '30d':
        days = 30
    elif time_range == '90d':
        days = 90
    else:
        days = 30
    
    start_date = timezone.now() - timedelta(days=days)
    
    # SMS analytics
    sms_data = SMSMessage.objects.filter(
        user=user,
        created_at__gte=start_date
    ).annotate(
        date=TruncDay('created_at')
    ).values('date', 'direction').annotate(
        count=Count('id'),
        total_price=Sum('price')
    ).order_by('date')
    
    # Call analytics
    call_data = CallLog.objects.filter(
        user=user,
        start_time__gte=start_date
    ).annotate(
        date=TruncDay('start_time')
    ).values('date', 'direction').annotate(
        count=Count('id'),
        total_duration=Sum('duration'),
        total_price=Sum('price')
    ).order_by('date')
    
    # Wallet analytics
    wallet_data = WalletTransaction.objects.filter(
        user=user,
        created_at__gte=start_date
    ).annotate(
        date=TruncDay('created_at')
    ).values('date', 'tx_type').annotate(
        count=Count('id'),
        total_amount=Sum('amount')
    ).order_by('date')
    
    # Top numbers by usage
    top_sms_numbers = user.phone_numbers.annotate(
        sms_count=Count('sms_messages'),
        call_count=Count('calls')
    ).order_by('-sms_count')[:5]
    
    top_call_numbers = user.phone_numbers.annotate(
        call_duration=Sum('calls__duration')
    ).order_by('-call_duration')[:5]
    
    context = {
        'sms_data': list(sms_data),
        'call_data': list(call_data),
        'wallet_data': list(wallet_data),
        'top_sms_numbers': top_sms_numbers,
        'top_call_numbers': top_call_numbers,
        'time_range': time_range,
        'days': days,
    }
    
    return render(request, 'user_dashboard/analytics.html', context)

# ==================== API ENDPOINTS ====================

@login_required
@require_http_methods(["GET"])
def api_dashboard_stats(request):
    """API endpoint for dashboard stats"""
    user = request.user
    
    # Get wallet
    wallet = user.wallet
    
    # Get counts
    stats = {
        'wallet_balance': float(wallet.balance),
        'phone_numbers': user.phone_numbers.filter(status='active').count(),
        'total_sms': user.sms_messages.count(),
        'total_calls': user.calls.count(),
        'unread_notifications': user.notifications.filter(is_read=False).count(),
        'pending_transactions': user.transactions.filter(status='pending').count(),
    }
    
    return JsonResponse({'success': True, 'data': stats})

@login_required
@require_http_methods(["POST"])
def api_send_sms(request):
    """API endpoint to send SMS"""
    try:
        data = json.loads(request.body)
        
        phone_number_id = data.get('phone_number_id')
        to_number = data.get('to_number')
        message = data.get('message')
        
        if not all([phone_number_id, to_number, message]):
            return JsonResponse({
                'success': False,
                'error': 'Missing required fields'
            })
        
        # Get phone number
        phone_number = get_object_or_404(
            UserPhoneNumber, 
            id=phone_number_id, 
            user=request.user,
            status='active',
            supports_sms=True
        )
        
        # Calculate cost
        segments = (len(message) // 160) + 1
        sms_cost = Decimal('0.01') * segments
        
        # Check balance
        wallet = request.user.wallet
        if wallet.balance < sms_cost:
            return JsonResponse({
                'success': False,
                'error': 'Insufficient balance'
            })
        
        # Create SMS record
        twilio_sid = f"SM{uuid.uuid4().hex[:32].upper()}"
        sms = SMSMessage.objects.create(
            twilio_sid=twilio_sid,
            user=request.user,
            phone_number=phone_number,
            sender=phone_number.phone_number,
            receiver=to_number,
            body=message,
            direction='outbound',
            status='sent',  # In production, would start as 'queued'
            segments=segments,
            price=sms_cost,
            created_at=timezone.now()
        )
        
        # Create transaction
        WalletTransaction.objects.create(
            user=request.user,
            tx_type='sms',
            amount=sms_cost,
            reference=f"SMS-{uuid.uuid4().hex[:8].upper()}",
            status='success',
            metadata={
                'sms_id': str(sms.id),
                'to_number': to_number,
                'segments': segments,
            }
        )
        
        return JsonResponse({
            'success': True,
            'message': 'SMS sent successfully',
            'data': {
                'sms_id': str(sms.id),
                'message_sid': twilio_sid,
                'cost': float(sms_cost),
                'segments': segments,
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

# ==================== TWILIO WEBHOOKS ====================

@csrf_exempt
@require_http_methods(["POST"])
def twilio_sms_webhook(request):
    """Handle Twilio SMS webhooks"""
    try:
        # Log the webhook
        event_sid = request.POST.get('MessageSid', f"WEBHOOK-{uuid.uuid4().hex[:16]}")
        
        webhook_log = TwilioWebhookLog.objects.create(
            event_sid=event_sid,
            event_type='sms_status_update',
            account_sid=request.POST.get('AccountSid'),
            payload=dict(request.POST)
        )
        
        # Process SMS status update
        message_sid = request.POST.get('MessageSid')
        message_status = request.POST.get('MessageStatus')
        
        if message_sid and message_status:
            try:
                sms = SMSMessage.objects.get(twilio_sid=message_sid)
                sms.status = message_status.lower()
                sms.save()
                
                # Mark webhook as processed
                webhook_log.processed = True
                webhook_log.save()
                
                return HttpResponse(status=200)
                
            except SMSMessage.DoesNotExist:
                webhook_log.processing_error = f"SMS not found: {message_sid}"
                webhook_log.save()
        
        return HttpResponse(status=200)
        
    except Exception as e:
        return HttpResponse(status=500)

@csrf_exempt
@require_http_methods(["POST"])
def twilio_inbound_sms_webhook(request):
    """Handle inbound SMS from Twilio"""
    try:
        # Log webhook
        event_sid = request.POST.get('MessageSid', f"INBOUND-{uuid.uuid4().hex[:16]}")
        
        webhook_log = TwilioWebhookLog.objects.create(
            event_sid=event_sid,
            event_type='inbound_sms',
            account_sid=request.POST.get('AccountSid'),
            payload=dict(request.POST)
        )
        
        # Extract data
        from_number = request.POST.get('From')
        to_number = request.POST.get('To')
        body = request.POST.get('Body')
        message_sid = request.POST.get('MessageSid')
        
        # Find the phone number
        try:
            phone_number = UserPhoneNumber.objects.get(phone_number=to_number)
            user = phone_number.user
            
            # Create inbound SMS record
            sms = SMSMessage.objects.create(
                twilio_sid=message_sid,
                user=user,
                phone_number=phone_number,
                sender=from_number,
                receiver=to_number,
                body=body,
                direction='inbound',
                status='received',
                segments=1,
                created_at=timezone.now()
            )
            
            # Create notification
            Notification.objects.create(
                user=user,
                notification_type='sms',
                title='New SMS Received',
                message=f'From {from_number}: {body[:50]}...',
                action_url=f'/dashboard/sms/{sms.id}/'
            )
            
            webhook_log.processed = True
            webhook_log.save()
            
            return HttpResponse(status=200)
            
        except UserPhoneNumber.DoesNotExist:
            webhook_log.processing_error = f"Phone number not found: {to_number}"
            webhook_log.save()
            return HttpResponse(status=200)
        
    except Exception as e:
        return HttpResponse(status=500)

@csrf_exempt
@require_http_methods(["POST"])
def twilio_voice_webhook(request):
    """Handle Twilio voice webhooks"""
    try:
        event_sid = request.POST.get('CallSid', f"VOICE-{uuid.uuid4().hex[:16]}")
        
        webhook_log = TwilioWebhookLog.objects.create(
            event_sid=event_sid,
            event_type='voice_status_update',
            account_sid=request.POST.get('AccountSid'),
            payload=dict(request.POST)
        )
        
        # Process call status
        call_sid = request.POST.get('CallSid')
        call_status = request.POST.get('CallStatus')
        
        if call_sid and call_status:
            try:
                call = CallLog.objects.get(twilio_sid=call_sid)
                call.status = call_status.lower()
                call.save()
                
                webhook_log.processed = True
                webhook_log.save()
                
            except CallLog.DoesNotExist:
                webhook_log.processing_error = f"Call not found: {call_sid}"
                webhook_log.save()
        
        return HttpResponse(status=200)
        
    except Exception as e:
        return HttpResponse(status=500)

# ==================== UTILITY VIEWS ====================

@login_required
def settings_view(request):
    """User settings"""
    user = request.user
    
    if request.method == 'POST':
        # Handle settings update
        try:
            data = json.loads(request.body)
            
            # Update user profile
            if 'first_name' in data:
                user.first_name = data['first_name']
            if 'last_name' in data:
                user.last_name = data['last_name']
            
            user.save()
            
            # Update user profile (if exists)
            if hasattr(user, 'profile'):
                profile = user.profile
                if 'phone_number' in data:
                    profile.phone_number = data['phone_number']
                if 'country' in data:
                    profile.country = data['country']
                profile.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Settings updated successfully'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid data format'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return render(request, 'user_dashboard/settings.html')

@login_required
def help_support_view(request):
    """Help and support"""
    return render(request, 'user_dashboard/help.html')

# ==================== ADMIN VIEWS (for dropshipping) ====================

@login_required
def admin_dashboard_view(request):
    """Admin dashboard for dropshipping"""
    if not request.user.is_staff:
        return redirect('dashboard')
    
    # Admin stats
    stats = {
        'total_users': User.objects.count(),
        'active_users': User.objects.filter(is_active=True).count(),
        'total_numbers': UserPhoneNumber.objects.count(),
        'total_sms': SMSMessage.objects.count(),
        'total_calls': CallLog.objects.count(),
        'total_revenue': WalletTransaction.objects.filter(
            tx_type__in=['purchase', 'sms', 'mms', 'call', 'renewal']
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
    }
    
    # Recent signups
    recent_signups = User.objects.filter(is_active=True).order_by('-date_joined')[:10]
    
    # Recent transactions
    recent_transactions = WalletTransaction.objects.all().order_by('-created_at')[:10]
    
    context = {
        'stats': stats,
        'recent_signups': recent_signups,
        'recent_transactions': recent_transactions,
    }
    
    return render(request, 'user_dashboard/admin/dashboard.html', context)

@login_required
def admin_users_view(request):
    """Admin user management"""
    if not request.user.is_staff:
        return redirect('dashboard')
    
    users = User.objects.all().order_by('-date_joined')
    
    # Search
    search_query = request.GET.get('search', '')
    if search_query:
        users = users.filter(
            Q(email__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query)
        )
    
    # Filter
    status_filter = request.GET.get('status', 'all')
    if status_filter == 'active':
        users = users.filter(is_active=True)
    elif status_filter == 'inactive':
        users = users.filter(is_active=False)
    
    # Pagination
    paginator = Paginator(users, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
    }
    
    return render(request, 'user_dashboard/admin/users.html', context)

@login_required
def admin_transactions_view(request):
    """Admin transaction management"""
    if not request.user.is_staff:
        return redirect('dashboard')
    
    transactions = WalletTransaction.objects.all().order_by('-created_at')
    
    # Filters
    transaction_type = request.GET.get('type', 'all')
    status_filter = request.GET.get('status', 'all')
    
    if transaction_type != 'all':
        transactions = transactions.filter(tx_type=transaction_type)
    
    if status_filter != 'all':
        transactions = transactions.filter(status=status_filter)
    
    # Pagination
    paginator = Paginator(transactions, 100)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'transaction_types': WalletTransaction.TRANSACTION_TYPE,
        'selected_type': transaction_type,
        'selected_status': status_filter,
    }
    
    return render(request, 'user_dashboard/admin/transactions.html', context)