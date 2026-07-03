from django.conf import settings

def global_settings(request):
    db_engine = settings.DATABASES.get('default', {}).get('ENGINE', '')
    is_oracle = 'oracle' in db_engine.lower()
    
    storage_backend = settings.STORAGES.get('default', {}).get('BACKEND', '')
    is_azure = 'azure' in storage_backend.lower()
    
    return {
        'active_db': 'Oracle OCI' if is_oracle else 'SQLite Local',
        'is_oracle_db': is_oracle,
        'storage_type': 'Azure Blobs' if is_azure else 'Local',
        'debug_mode': settings.DEBUG,
    }
