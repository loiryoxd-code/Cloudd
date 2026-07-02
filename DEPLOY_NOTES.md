# Guía de Despliegue en AWS EC2 (Ubuntu) con Nginx, Gunicorn, OCI DB y Azure Storage

Esta guía contiene los pasos y comandos exactos para desplegar el proyecto Django **SecureDocs** en una instancia AWS EC2 corriendo Ubuntu Server (22.04 LTS o 24.04 LTS).

---

## Requisitos de Sistema en la Instancia EC2

Actualiza el sistema e instala los paquetes necesarios para Python y el servidor web:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3-pip python3-venv python3-dev nginx git -y
```

> [!NOTE]
> La librería `oracledb` de Python funciona por defecto en **Thin Mode** (Modo Delgado), lo cual significa que **no requiere** la instalación de la pesada paquetería de Oracle Instant Client en la máquina host. Solo requiere acceso a la red de la base de datos y la Wallet.

---

## 1. Clonar el Proyecto y Configurar el Virtualenv

Clona tu repositorio en la ruta recomendada (por ejemplo, `/var/www/securedocs`):

```bash
sudo mkdir -p /var/www/securedocs
sudo chown -R ubuntu:ubuntu /var/www/securedocs
cd /var/www/securedocs

# Clona el proyecto (reemplaza con tu url real o súbelo por SCP/SFTP)
# git clone <URL_DEL_REPOSITORIO> .

# Crear y activar el entorno virtual
python3 -m venv venv
source venv/bin/activate

# Actualizar pip e instalar dependencias
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 2. Configurar Variables de Entorno (.env)

Copia la plantilla de configuración de variables de entorno y edítala con tus credenciales de producción:

```bash
cp .env.example .env
nano .env
```

Asegúrate de configurar adecuadamente:
* `SECRET_KEY`: Genera una clave segura.
* `DEBUG=False`: Desactivado para producción para evitar fugas de información (OWASP A05:2021).
* `ALLOWED_HOSTS`: La dirección IP pública de la instancia EC2 y tu dominio (ej. `198.51.100.12,mi-dominio.com`).
* `CSRF_TRUSTED_ORIGINS`: Las URLs de origen confiable (ej. `http://198.51.100.12,https://mi-dominio.com`).
* Variables de OCI Autonomous Database (si vas a usar la base de datos en nube).
* Variables de Azure Blob Storage (si usarás almacenamiento Azure para medios/estáticos).

---

## 3. Configuración de Oracle OCI Wallet

Para conectar con Oracle Autonomous Database mediante Wallet:

1. Descarga el archivo zip de la Wallet (ej. `Wallet_DBNAME.zip`) desde la consola de OCI.
2. Crea un directorio llamado `wallet` en la raíz del proyecto (este directorio ya está en el `.gitignore`):
   ```bash
   mkdir -p /var/www/securedocs/wallet
   ```
3. Descomprime los archivos dentro de esa carpeta.
4. Modifica el archivo `sqlnet.ora` dentro del directorio `wallet` para que apunte al directorio correcto. Asegúrate de cambiar el parámetro `DIRECTORY` de la siguiente forma:
   ```text
   WALLET_LOCATION = (SOURCE = (METHOD = file) (METHOD_DATA = (DIRECTORY="/var/www/securedocs/wallet")))
   ```
5. En tu archivo `.env`, define la variable `OCI_WALLET_DIR` apuntando a esa ruta absoluta:
   ```text
   OCI_WALLET_DIR=/var/www/securedocs/wallet
   ```

---

## 4. Ejecutar Migraciones y Recolectar Estáticos

Con el entorno virtual activado y las variables cargadas, ejecuta:

```bash
# Ejecutar comprobación de seguridad de despliegue sugerida por Django
python manage.py check --deploy

# Ejecutar las migraciones de base de datos
python manage.py migrate

# Recolectar los archivos estáticos
# (Si Azure Storage está activo en el .env, se subirán automáticamente a Azure Blob Storage;
# de lo contrario, se guardarán localmente en staticfiles/)
python manage.py collectstatic --noinput
```

---

## 5. Configuración de Gunicorn (Servicio Systemd)

Gunicorn se ejecutará en segundo plano administrado por `systemd`.

### Crear el Socket de Gunicorn

Crea el archivo `/etc/systemd/system/gunicorn.socket`:

```bash
sudo nano /etc/systemd/system/gunicorn.socket
```

Inserta la siguiente configuración:

```ini
[Unit]
Description=gunicorn socket

[Socket]
ListenStream=/run/gunicorn.sock

[Install]
WantedBy=sockets.target
```

### Crear el Servicio de Gunicorn

Crea el archivo de servicio `/etc/systemd/system/gunicorn.service`:

```bash
sudo nano /etc/systemd/system/gunicorn.service
```

Inserta la siguiente configuración (ajusta las rutas si decidiste clonar en otra ubicación):

```ini
[Unit]
Description=gunicorn daemon
Requires=gunicorn.socket
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/var/www/securedocs
ExecStart=/var/www/securedocs/venv/bin/gunicorn \
          --access-logfile - \
          --workers 3 \
          --bind unix:/run/gunicorn.sock \
          securedocs.wsgi:application

[Install]
WantedBy=multi-user.target
```

### Iniciar y Habilitar Gunicorn

Ejecuta los siguientes comandos para arrancar Gunicorn al inicio del sistema:

```bash
sudo systemctl start gunicorn.socket
sudo systemctl enable gunicorn.socket

# Verificar estado
sudo systemctl status gunicorn.socket
```

---

## 6. Configuración de Nginx (Proxy Reverso)

Nginx recibirá las conexiones del puerto 80 (HTTP) y las redirigirá al socket de Gunicorn.

Crea el archivo de sitio `/etc/nginx/sites-available/securedocs`:

```bash
sudo nano /etc/nginx/sites-available/securedocs
```

Inserta la siguiente configuración (reemplaza `198.51.100.12` por tu IP o dominio público):

```nginx
server {
    listen 80;
    server_name 198.51.100.12;

    # Evitar revelar versión de Nginx en cabeceras de error (A05:2021)
    server_tokens off;

    # Denegar accesos de clickjacking (Mitigación OWASP)
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "same-origin" always;

    # Archivo de logs de acceso y errores
    access_log /var/log/nginx/securedocs_access.log;
    error_log /var/log/nginx/securedocs_error.log;

    # Fallback para archivos estáticos locales (si no se usa Azure Storage en producción)
    location /static/ {
        alias /var/www/securedocs/staticfiles/;
    }

    # Fallback para archivos multimedia locales (si no se usa Azure Storage en producción)
    location /media/ {
        alias /var/www/securedocs/media/;
    }

    # Redirección al Socket de Gunicorn
    location / {
        include proxy_params;
        proxy_pass http://unix:/run/gunicorn.sock;
    }
}
```

### Habilitar el sitio y reiniciar Nginx

```bash
# Enlazar archivo para habilitar el sitio
sudo ln -s /etc/nginx/sites-available/securedocs /etc/nginx/sites-enabled/

# Validar sintaxis de configuración de Nginx
sudo nginx -t

# Si la prueba es exitosa, reiniciar Nginx
sudo systemctl restart nginx

# Habilitar tráfico HTTP en el firewall de Ubuntu (UFW) si está activo
sudo ufw allow 'Nginx Full'
```

---

## 7. Notas sobre CI/CD (GitHub Actions)

Una vez que el despliegue manual esté verificado y la aplicación esté en funcionamiento seguro, puedes implementar la automatización de CI/CD:

1. Crea un workflow de GitHub en `.github/workflows/deploy.yml`.
2. El workflow puede:
   * Correr tests automatizados en cada Push (`python manage.py test`).
   * Usar un cliente SSH o rsync para subir el código a la instancia EC2.
   * Ejecutar de forma remota: `source venv/bin/activate && pip install -r requirements.txt && python manage.py migrate && python manage.py collectstatic --noinput && sudo systemctl restart gunicorn`.
3. Configura los secretos del repositorio en GitHub (`SSH_PRIVATE_KEY`, `EC2_HOST`, `EC2_USER`) para realizar el inicio seguro de sesión SSH desde los corredores virtuales de GitHub.
