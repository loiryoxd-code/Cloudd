from .models import SecurityAuditLog

def log_security_event(request, action, details, severity='INFO', user=None):
    """
    Logs a security event to the database for auditing and monitoring.
    Maps to OWASP A09:2021-Security Logging and Monitoring Failures.
    """
    resolved_user = user
    if not resolved_user and request and request.user and request.user.is_authenticated:
        resolved_user = request.user
        
    ip = None
    agent = None
    if request:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        agent = request.META.get('HTTP_USER_AGENT', '')[:255]
        
    SecurityAuditLog.objects.create(
        action=action,
        user=resolved_user,
        ip_address=ip,
        user_agent=agent,
        details=details,
        severity=severity
    )
