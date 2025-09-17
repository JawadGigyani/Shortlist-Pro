import random
import string
import secrets
from datetime import timedelta
from django.utils import timezone

def generate_otp(length=6):
    """Generate a secure random OTP code"""
    # Use secrets module for cryptographically secure random numbers
    characters = string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))

def is_otp_expired(sent_at, expiry_minutes=10):
    """Check if OTP has expired"""
    if not sent_at:
        return True
    expiry_time = sent_at + timedelta(minutes=expiry_minutes)
    return timezone.now() > expiry_time

def can_resend_otp(last_sent_at, cooldown_minutes=1):
    """Check if user can request a new OTP (rate limiting)"""
    if not last_sent_at:
        return True
    cooldown_time = last_sent_at + timedelta(minutes=cooldown_minutes)
    return timezone.now() > cooldown_time

def format_phone_number(phone):
    """Format phone number for display"""
    if not phone:
        return ""
    # Remove all non-digit characters
    digits = ''.join(filter(str.isdigit, phone))
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    elif len(digits) == 11 and digits[0] == '1':
        return f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    return phone

def mask_email(email):
    """Mask email address for privacy"""
    if not email or '@' not in email:
        return email
    
    username, domain = email.split('@', 1)
    if len(username) <= 2:
        masked_username = username[0] + '*' * (len(username) - 1)
    else:
        masked_username = username[0] + '*' * (len(username) - 2) + username[-1]
    
    return f"{masked_username}@{domain}"

def validate_otp_format(otp_code):
    """Validate OTP format (6 digits)"""
    if not otp_code:
        return False, "OTP code is required"
    
    if not otp_code.isdigit():
        return False, "OTP must contain only numbers"
    
    if len(otp_code) != 6:
        return False, "OTP must be exactly 6 digits"
    
    return True, "Valid format"