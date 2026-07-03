from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

def db_diagnostic_view(request):
    from django.http import JsonResponse
    from django.db import connection
    from django.conf import settings
    from django.contrib.auth.models import User
    import os
    
    db_info = {}
    for alias, config in settings.DATABASES.items():
        db_info[alias] = {
            'ENGINE': config.get('ENGINE'),
            'NAME': config.get('NAME'),
            'USER': config.get('USER'),
            'HOST': config.get('HOST'),
            'PORT': config.get('PORT'),
        }
    
    users = list(User.objects.values('id', 'username', 'email', 'date_joined'))
    # format date_joined to string
    for u in users:
        u['date_joined'] = u['date_joined'].isoformat()
        
    return JsonResponse({
        'vendor': connection.vendor,
        'databases': db_info,
        'users': users,
        'env_keys_filtered': {k: v for k, v in os.environ.items() if 'OCI' in k or 'DB' in k or 'WALLET' in k or 'PORT' in k or 'HOST' in k},
        'all_env_keys': list(os.environ.keys()),
    })

urlpatterns = [
    path('db-diagnostic-endpoint/', db_diagnostic_view),
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('documents/', include('documents.urls')),
]

# Support local media serving in development mode
if settings.DEFAULT_FILE_STORAGE == 'django.core.files.storage.FileSystemStorage':
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
