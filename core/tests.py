from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from core.models import SecurityAuditLog
from documents.models import Document
from django.core.files.uploadedfile import SimpleUploadedFile

class SecurityTestCase(TestCase):
    def setUp(self):
        # Create users
        self.admin_user = User.objects.create_superuser('admin', 'admin@example.com', 'AdminPassword123')
        self.standard_user = User.objects.create_user('user', 'user@example.com', 'UserPassword123')
        
        # Initialize client
        self.client = Client()

    def test_landing_page(self):
        """Verify the landing page is accessible when unauthenticated."""
        response = self.client.get(reverse('landing'))
        self.assertEqual(response.status_code, 200)

    def test_dashboard_redirects_unauthenticated(self):
        """Verify that dashboard redirects to login if user is not authenticated."""
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_dashboard_accessible_when_authenticated(self):
        """Verify dashboard is accessible when authenticated."""
        self.client.force_login(self.standard_user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_broken_access_control_prevention(self):
        """
        Verify that a standard user cannot access the administrator panel.
        Ensures OWASP A01:2021 mitigation.
        """
        self.client.force_login(self.standard_user)
        response = self.client.get(reverse('admin_users'))
        self.assertEqual(response.status_code, 403) # Forbidden
        
        # Verify an access violation was logged in the security audits table
        log_exists = SecurityAuditLog.objects.filter(action='ACCESS_DENIED', severity='CRITICAL').exists()
        self.assertTrue(log_exists)

    def test_admin_access_allowed(self):
        """Verify that an admin user can access the admin panel."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('admin_users'))
        self.assertEqual(response.status_code, 200)

    def test_document_owner_isolation(self):
        """
        Verify that a user cannot see or download another user's documents.
        Ensures OWASP A01:2021 mitigation.
        """
        # Upload a document for the admin
        test_file = SimpleUploadedFile("evidence.pdf", b"file_content", content_type="application/pdf")
        doc = Document.objects.create(
            owner=self.admin_user,
            title="Confidential Admin Doc",
            description="Top secret notes",
            file=test_file
        )
        
        # Login as standard user and try to view detail
        self.client.force_login(self.standard_user)
        response = self.client.get(reverse('documents:detail', args=[doc.pk]))
        self.assertEqual(response.status_code, 403) # Forbidden
        
        # Try to download
        response_download = self.client.get(reverse('documents:download', args=[doc.pk]))
        self.assertEqual(response_download.status_code, 403) # Forbidden

    def test_cryptographic_failures_mitigation(self):
        """
        Verify metadata encryption works for A02:2021.
        """
        test_file = SimpleUploadedFile("confidencial.txt", b"plain_text_data", content_type="text/plain")
        doc = Document.objects.create(
            owner=self.standard_user,
            title="My Doc",
            file=test_file
        )
        # Encrypt sensitive notes
        doc.encrypt_notes("This is highly confidential metadata.")
        doc.save()
        
        # Fetch directly from database and verify they are stored encrypted
        fetched_doc = Document.objects.get(pk=doc.pk)
        self.assertNotEqual(fetched_doc.encrypted_notes, "This is highly confidential metadata.")
        self.assertTrue(len(fetched_doc.encrypted_notes) > 0)
        
        # Verify it decrypts back correctly
        self.assertEqual(fetched_doc.decrypt_notes(), "This is highly confidential metadata.")

    def test_file_integrity_hash(self):
        """
        Verify SHA-256 hash is computed on save for A08:2021.
        """
        test_file = SimpleUploadedFile("test.txt", b"my_file_data_here", content_type="text/plain")
        doc = Document.objects.create(
            owner=self.standard_user,
            title="Integrity Doc",
            file=test_file
        )
        
        # Check if hash matches SHA-256 of b"my_file_data_here"
        import hashlib
        expected_hash = hashlib.sha256(b"my_file_data_here").hexdigest()
        self.assertEqual(doc.file_hash, expected_hash)

    def test_db_diagnostic_accessible_in_debug(self):
        """Verify that db-diagnostic page is accessible to admin when DEBUG=True."""
        self.client.force_login(self.admin_user)
        with self.settings(DEBUG=True):
            response = self.client.get(reverse('db_diagnostic'))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Diagnóstico de Base de Datos")

    def test_db_diagnostic_forbidden_in_production(self):
        """Verify that db-diagnostic page is forbidden even to admin when DEBUG=False."""
        self.client.force_login(self.admin_user)
        with self.settings(DEBUG=False):
            response = self.client.get(reverse('db_diagnostic'))
            self.assertEqual(response.status_code, 403)

    def test_db_diagnostic_forbidden_for_standard_user(self):
        """Verify that a standard user cannot access the diagnostic page even in debug."""
        self.client.force_login(self.standard_user)
        with self.settings(DEBUG=True):
            response = self.client.get(reverse('db_diagnostic'))
            self.assertEqual(response.status_code, 403)

    def test_db_diagnostic_redirects_unauthenticated(self):
        """Verify that unauthenticated requests redirect to login."""
        with self.settings(DEBUG=True):
            response = self.client.get(reverse('db_diagnostic'))
            self.assertEqual(response.status_code, 302)


