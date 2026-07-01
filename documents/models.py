import hashlib
from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from cryptography.fernet import Fernet

class Document(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documents')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to='evidences/')
    
    # Integrity Tracking (OWASP A08:2021)
    file_hash = models.CharField(max_length=64, blank=True, verbose_name="Hash SHA-256")
    file_size = models.IntegerField(default=0, verbose_name="Tamaño (bytes)")
    content_type = models.CharField(max_length=150, blank=True, verbose_name="Tipo MIME")
    
    # Cryptographic Failures Mitigation (OWASP A02:2021)
    # Encrypted notes/metadata for extra sensitivity
    encrypted_notes = models.TextField(blank=True, verbose_name="Notas encriptadas en reposo")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # Calculate SHA-256 hash and size of the file on upload
        if self.file and (not self.file_hash or 'file' in self.get_dirty_fields() if hasattr(self, 'get_dirty_fields') else True):
            hasher = hashlib.sha256()
            try:
                # Read chunks to prevent memory blowup (denial of service)
                for chunk in self.file.chunks():
                    hasher.update(chunk)
                self.file_hash = hasher.hexdigest()
                self.file_size = self.file.size
                
                # Retrieve content type if possible
                if hasattr(self.file, 'content_type'):
                    self.content_type = self.file.content_type
                else:
                    import mimetypes
                    self.content_type = mimetypes.guess_type(self.file.name)[0] or 'application/octet-stream'
            except Exception:
                pass # Fallback in case of storage mockups
                
        super().save(*args, **kwargs)

    # Cryptographic Helpers for Encrypted Notes
    def encrypt_notes(self, plaintext_notes):
        """Encrypts notes using Fernet encryption key from settings."""
        if not plaintext_notes:
            self.encrypted_notes = ""
            return
        
        try:
            key = settings.ENCRYPTION_KEY.encode()
            f = Fernet(key)
            encrypted_data = f.encrypt(plaintext_notes.encode())
            self.encrypted_notes = encrypted_data.decode()
        except Exception as e:
            self.encrypted_notes = f"ERROR_ENCRYPTING: {str(e)}"

    def decrypt_notes(self):
        """Decrypts and returns notes, or empty string on failure."""
        if not self.encrypted_notes or self.encrypted_notes.startswith("ERROR_"):
            return ""
        
        try:
            key = settings.ENCRYPTION_KEY.encode()
            f = Fernet(key)
            decrypted_data = f.decrypt(self.encrypted_notes.encode())
            return decrypted_data.decode()
        except Exception:
            return "[Error decodificando notas cifradas: Llave inválida]"
