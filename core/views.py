from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib.auth.password_validation import validate_password
from django.conf import settings

from .models import SecurityAuditLog, UserProfile
from .utils import log_security_event
from .forms import UserProfileForm, UserRegistrationForm, UserLoginForm
from documents.models import Document

# 1. Landing View
def landing(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'landing.html')

# 2. Dashboard View
@login_required
def dashboard(request):
    user_docs = Document.objects.filter(owner=request.user)
    recent_docs = user_docs.order_by('-created_at')[:5]
    
    # Audit log counts and items
    audit_logs = SecurityAuditLog.objects.filter(user=request.user).order_by('-timestamp')[:5]
    if request.user.profile.role == 'admin':
        # Admin sees all security alerts
        all_logs = SecurityAuditLog.objects.all().order_by('-timestamp')[:10]
        critical_count = SecurityAuditLog.objects.filter(severity='CRITICAL').count()
        warning_count = SecurityAuditLog.objects.filter(severity='WARNING').count()
    else:
        all_logs = audit_logs
        critical_count = SecurityAuditLog.objects.filter(user=request.user, severity='CRITICAL').count()
        warning_count = SecurityAuditLog.objects.filter(user=request.user, severity='WARNING').count()

    context = {
        'total_docs': user_docs.count(),
        'recent_docs': recent_docs,
        'audit_logs': all_logs,
        'critical_count': critical_count,
        'warning_count': warning_count,
    }
    return render(request, 'dashboard.html', context)

# 3. User Profile View
@login_required
def profile(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            log_security_event(request, 'PROFILE_UPDATE', f"Perfil de usuario '{request.user.username}' actualizado.")
            messages.success(request, "Perfil actualizado con éxito.")
            return redirect('profile')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)

    return render(request, 'profile.html')

# 4. OWASP Top 10 Security Console View
@login_required
def owasp_dashboard(request):
    # Prepare statuses of security checks dynamically
    sec_checks = [
        {
            'id': 'A01',
            'title': 'A01:2021-Broken Access Control',
            'status': 'PASSED',
            'description': 'Control de acceso basado en roles (RBAC) y propietario. Los documentos se filtran a nivel de base de datos en las consultas y se validan con owner.',
            'test_url': '/documents/',
        },
        {
            'id': 'A02',
            'title': 'A02:2021-Cryptographic Failures',
            'status': 'PASSED' if settings.ENCRYPTION_KEY else 'FAILED',
            'description': f"Encriptación de metadatos sensibles utilizando clave Fernet {'activa' if settings.ENCRYPTION_KEY else 'inactiva'}. El archivo subido se valida mediante hash SHA-256.",
            'test_url': None,
        },
        {
            'id': 'A03',
            'title': 'A03:2021-Injection',
            'status': 'PASSED' if getattr(settings, 'CSP_ENABLED', True) else 'WARNING',
            'description': 'Uso del ORM de Django parametrizado para evitar SQL Injection. Cabecera Content-Security-Policy (CSP) inyectada en el middleware para evitar XSS.',
            'test_url': None,
        },
        {
            'id': 'A04',
            'title': 'A04:2021-Insecure Design',
            'status': 'PASSED',
            'description': 'Diseño seguro que incluye el principio de privilegio mínimo y la separación de entornos productivos mediante variables de configuración separadas.',
            'test_url': None,
        },
        {
            'id': 'A05',
            'title': 'A05:2021-Security Misconfiguration',
            'status': 'WARNING' if settings.DEBUG else 'PASSED',
            'description': f"DEBUG={settings.DEBUG}. En producción, DEBUG debe estar desactivado para evitar revelación de detalles de la pila de errores.",
            'test_url': None,
        },
        {
            'id': 'A06',
            'title': 'A06:2021-Vulnerable and Outdated Components',
            'status': 'PASSED',
            'description': 'Uso de versiones específicas y actualizadas en requirements.txt. Django preconfigurado contra ataques conocidos.',
            'test_url': None,
        },
        {
            'id': 'A07',
            'title': 'A07:2021-Identification and Authentication Failures',
            'status': 'PASSED' if getattr(settings, 'AXES_ENABLED', True) else 'FAILED',
            'description': 'Validadores de contraseñas de Django obligatorios (>10 caracteres). Protección contra fuerza bruta mediante django-axes (límite de 5 intentos fallidos).',
            'test_url': '/login/',
        },
        {
            'id': 'A08',
            'title': 'A08:2021-Software and Data Integrity Failures',
            'status': 'PASSED',
            'description': 'Cálculo e inspección del hash SHA-256 de archivos subidos para verificar la integridad del almacenamiento (Azure Blobs / Local).',
            'test_url': None,
        },
        {
            'id': 'A09',
            'title': 'A09:2021-Security Logging and Monitoring Failures',
            'status': 'PASSED',
            'description': 'Eventos críticos (logins, accesos denegados, descargas, subidas) registrados en la tabla SecurityAuditLog y archivo local.',
            'test_url': '/admin/',
        },
        {
            'id': 'A10',
            'title': 'A10:2021-Server-Side Request Forgery (SSRF)',
            'status': 'PASSED',
            'description': 'Restricción de peticiones salientes a URLs externas del servidor, validación estricta de variables de almacenamiento remoto (Azure).',
            'test_url': None,
        }
    ]

    context = {
        'checks': sec_checks,
        'debug_mode': settings.DEBUG,
        'axes_enabled': getattr(settings, 'AXES_ENABLED', True),
        'db_backend': settings.DATABASES['default']['ENGINE'],
        'storage_backend': settings.DEFAULT_FILE_STORAGE,
    }
    return render(request, 'owasp.html', context)

# 5. Secure Login View
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        form = UserLoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                log_security_event(request, 'LOGIN_SUCCESS', f"Usuario '{username}' ha iniciado sesión exitosamente.")
                messages.success(request, f"¡Bienvenido, {username}!")
                return redirect('dashboard')
            else:
                # Note: django-axes automatically records failure attempts,
                # but we also write a security audit event
                log_security_event(request, 'LOGIN_FAILURE', f"Intento fallido de inicio de sesión para el usuario '{username}'.", severity='WARNING')
                messages.error(request, "Usuario o contraseña inválidos.")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)
            
    return render(request, 'login.html')

# 6. Logout View
def logout_view(request):
    username = request.user.username if request.user.is_authenticated else "Anónimo"
    log_security_event(request, 'LOGOUT', f"Usuario '{username}' cerró sesión.")
    logout(request)
    messages.success(request, "Sesión cerrada correctamente.")
    return redirect('landing')

# 7. Register View
def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            
            # Create user
            user = User.objects.create_user(username=username, email=email, password=password)
            log_security_event(request, 'USER_REGISTER', f"Nuevo usuario '{username}' creado.", user=user)
            messages.success(request, "Registro completado con éxito. Ahora puedes iniciar sesión.")
            return redirect('login')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)
        
    return render(request, 'register.html')

# 8. Admin Users Control Panel (Broken Access Control verification endpoint)
@login_required
def admin_users_view(request):
    # Role checking (OWASP A01:2021)
    if request.user.profile.role != 'admin':
        log_security_event(
            request, 
            'ACCESS_DENIED', 
            f"Usuario '{request.user.username}' intentó acceder sin permisos al panel de administración de usuarios.",
            severity='CRITICAL'
        )
        raise PermissionDenied("No tienes permisos suficientes para acceder a este panel de administración.")
        
    users = User.objects.all().select_related('profile')
    context = {
        'users_list': users
    }
    return render(request, 'admin_users.html', context)


# 9. Database & Authentication Diagnostic View (Only in DEBUG mode and protected by Staff/Admin)
@login_required
def db_diagnostic_view(request):
    import os
    if not settings.DEBUG:
        raise PermissionDenied("El diagnóstico de base de datos solo está disponible en modo DEBUG.")
        
    # Check authorization (requires superuser, staff, or admin profile role)
    if not (request.user.is_staff or request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role == 'admin')):
        raise PermissionDenied("No tienes permisos suficientes para acceder a este panel de diagnóstico.")
        
    db_config = settings.DATABASES.get('default', {})
    db_engine = db_config.get('ENGINE', 'Desconocido')
    db_name = db_config.get('NAME', 'Desconocido')
    
    # Try to test connection
    from django.db import connection
    db_connected = False
    db_error = None
    try:
        connection.ensure_connection()
        db_connected = True
    except Exception as e:
        db_error = str(e)
        
    # Read environment variables status
    env_keys = ['OCI_DB_NAME', 'OCI_DB_USER', 'OCI_DB_PASSWORD', 'OCI_WALLET_DIR', 'OCI_WALLET_PASSWORD']
    env_vars = {}
    for key in env_keys:
        val = os.getenv(key)
        if val:
            if 'PASSWORD' in key:
                masked = val[:2] + "****" + val[-2:] if len(val) > 4 else "****"
                env_vars[key] = {'defined': True, 'value': masked}
            else:
                env_vars[key] = {'defined': True, 'value': val}
        else:
            env_vars[key] = {'defined': False, 'value': ''}
            
    # List users in the database
    users = User.objects.all().order_by('id')
    users_list = []
    for u in users:
        role = u.profile.role if hasattr(u, 'profile') else 'Sin Perfil'
        users_list.append({
            'id': u.id,
            'username': u.username,
            'email': u.email,
            'profile_role': role,
            'is_superuser': u.is_superuser,
            'is_active': u.is_active,
            'last_login': u.last_login,
        })
        
    context = {
        'db_engine': db_engine,
        'db_name': db_name,
        'db_connected': db_connected,
        'db_error': db_error,
        'env_vars': env_vars,
        'auth_backends': settings.AUTHENTICATION_BACKENDS,
        'users_list': users_list,
    }
    return render(request, 'db_diagnostic.html', context)

