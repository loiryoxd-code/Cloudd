import os
import sys
from pathlib import Path

# Set up Django environment
BASE_DIR = Path(__file__).resolve().parent
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'securedocs.settings')

try:
    import django
    django.setup()
except ImportError:
    print("Error: Django could not be imported. Make sure to activate your virtual environment first.")
    print("Example: venv_win\\Scripts\\activate (Windows) or source venv/bin/activate (Unix)")
    sys.exit(1)

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection

def mask_value(val):
    if not val:
        return "None / Empty"
    if len(val) <= 4:
        return "****"
    return val[:2] + "****" + val[-2:]

def main():
    print("=" * 60)
    print("         DIAGNOSTICO DE BASE DE DATOS - SECUREDOCS")
    print("=" * 60)

    # 1. Environment Variables Configuration
    print("\n[1] Variables de Entorno (OCI / Oracle):")
    oci_keys = ['OCI_DB_NAME', 'OCI_DB_USER', 'OCI_DB_PASSWORD', 'OCI_WALLET_DIR', 'OCI_WALLET_PASSWORD']
    for key in oci_keys:
        val = os.getenv(key)
        if 'PASSWORD' in key:
            display_val = mask_value(val)
        else:
            display_val = val if val else "No definida (None)"
        print(f"  - {key}: {display_val}")

    # 2. Django DATABASE Settings
    print("\n[2] Configuración de DATABASES en Django:")
    db_config = settings.DATABASES.get('default', {})
    engine = db_config.get('ENGINE', 'Desconocido')
    db_name = db_config.get('NAME', 'Desconocido')
    db_user = db_config.get('USER', '')
    
    print(f"  - Motor (ENGINE): {engine}")
    print(f"  - Nombre de BD (NAME): {db_name}")
    if db_user:
        print(f"  - Usuario (USER): {db_user}")

    # 3. Connection Status
    print("\n[3] Prueba de Conexión Activa:")
    try:
        connection.ensure_connection()
        print("  - Estado de conexión: EXITOSA (Conectado a la base de datos)")
    except Exception as e:
        print(f"  - Estado de conexión: FALLIDA")
        print(f"  - Detalle del error: {str(e)}")

    # 4. Auth Backends Configuration
    print("\n[4] Backends de Autenticación Activos:")
    for backend in settings.AUTHENTICATION_BACKENDS:
        print(f"  - {backend}")

    # 5. User List in the Active Database
    print("\n[5] Usuarios Registrados en la Base de Datos Activa:")
    User = get_user_model()
    try:
        users = User.objects.all().order_by('id')
        user_count = users.count()
        print(f"  - Total de usuarios encontrados: {user_count}")
        if user_count > 0:
            print(f"  - {'ID':<4} | {'Usuario':<15} | {'Email':<25} | {'Rol (Profile)':<15} | {'Superuser':<10} | {'Activo':<8} | {'Último Login':<20}")
            print(f"    {'-'*110}")
            for u in users:
                # Try to get profile role
                role = "Sin Perfil"
                if hasattr(u, 'profile'):
                    role = u.profile.role
                
                last_login = u.last_login.strftime('%Y-%m-%d %H:%M:%S') if u.last_login else 'Nunca'
                print(f"  - {u.id:<4} | {u.username:<15} | {str(u.email):<25} | {role:<15} | {str(u.is_superuser):<10} | {str(u.is_active):<8} | {last_login:<20}")
        else:
            print("  - No hay usuarios creados en esta base de datos.")
    except Exception as e:
        print(f"  - Error al consultar usuarios: {str(e)}")

    # 6. SQLite Database File Check
    print("\n[6] Archivos de Base de Datos Locales:")
    sqlite_path = Path(settings.BASE_DIR) / 'db.sqlite3'
    if sqlite_path.exists():
        size_kb = sqlite_path.stat().st_size / 1024
        print(f"  - db.sqlite3 local detectado:")
        print(f"    * Ruta: {sqlite_path}")
        print(f"    * Tamaño: {size_kb:.2f} KB")
    else:
        print("  - No se detectó archivo db.sqlite3 en el directorio raíz.")

    print("\n" + "=" * 60)
    print("                    FIN DEL DIAGNOSTICO")
    print("=" * 60)

if __name__ == '__main__':
    main()
