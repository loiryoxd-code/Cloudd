from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from documents.models import Document
import base64

class DocumentSignatureAndPreviewTests(TestCase):
    def setUp(self):
        # Create two users
        self.owner = User.objects.create_user(username='owner', password='password123#')
        self.other_user = User.objects.create_user(username='other', password='password123#')
        
        # Simple test file
        self.test_file = SimpleUploadedFile("test.png", b"file_content_fake_png", content_type="image/png")
        
        # Base64 signature data (a dummy transparent 1x1 png)
        self.dummy_sig_base64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="

    def test_upload_document_with_signature(self):
        self.client.force_login(self.owner)
        
        # Test document create
        response = self.client.post(reverse('documents:create'), {
            'title': 'Test Document Signature',
            'description': 'Description text',
            'notes': 'Confidential notes',
            'file': self.test_file,
            'signature_data': self.dummy_sig_base64
        })
        
        # Assert redirected to detail
        self.assertEqual(response.status_code, 302)
        
        # Verify document saved with signature
        doc = Document.objects.filter(owner=self.owner).first()
        self.assertIsNotNone(doc)
        self.assertEqual(doc.title, 'Test Document Signature')
        self.assertIsNotNone(doc.signature_image)
        self.assertTrue(doc.signature_image.name.startswith('signatures/sig_'))
        
        # Check notes decrypted correctly
        self.assertEqual(doc.decrypt_notes(), 'Confidential notes')

    def test_secure_preview_ownership(self):
        # Create a document for owner without signature
        doc = Document.objects.create(
            owner=self.owner,
            title="Secure Image",
            file=SimpleUploadedFile("test.png", b"png_data", content_type="image/png"),
            content_type="image/png"
        )
        
        # 1. Owner cannot access preview when unsigned
        self.client.force_login(self.owner)
        response = self.client.get(reverse('documents:preview', args=[doc.pk]))
        self.assertEqual(response.status_code, 403)
        
        # 2. Add signature, but not authorized in session yet
        doc.signature_image = SimpleUploadedFile("sig.png", b"sig_data", content_type="image/png")
        doc.save()
        response = self.client.get(reverse('documents:preview', args=[doc.pk]))
        self.assertEqual(response.status_code, 403)

        # 3. Authorize in session, now Owner can access preview and it's inline
        import time
        session = self.client.session
        session['authorized_previews'] = {str(doc.pk): time.time()}
        session.save()
        response = self.client.get(reverse('documents:preview', args=[doc.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIn('inline', response['Content-Disposition'])
        
        # 4. Test expiration: set authorization time to 3 minutes ago
        session = self.client.session
        session['authorized_previews'] = {str(doc.pk): time.time() - 180}
        session.save()
        response = self.client.get(reverse('documents:preview', args=[doc.pk]))
        self.assertEqual(response.status_code, 403)

        # 5. Other logged-in user cannot access preview even if authorized in owner's session
        self.client.force_login(self.other_user)
        # Restore active session timestamp for other_user (who shouldn't be allowed anyway)
        session = self.client.session
        session['authorized_previews'] = {str(doc.pk): time.time()}
        session.save()
        response = self.client.get(reverse('documents:preview', args=[doc.pk]))
        self.assertEqual(response.status_code, 403)

    def test_secure_signature_preview_ownership(self):
        # Create a document with a signature for owner
        doc = Document.objects.create(
            owner=self.owner,
            title="Signed Document",
            file=SimpleUploadedFile("test.pdf", b"pdf_data", content_type="application/pdf"),
            signature_image=SimpleUploadedFile("sig.png", b"signature_png_data", content_type="image/png")
        )
        
        # 1. Owner cannot access signature preview if not authorized in session
        self.client.force_login(self.owner)
        response = self.client.get(reverse('documents:signature_preview', args=[doc.pk]))
        self.assertEqual(response.status_code, 403)

        # 2. Owner can access signature preview when authorized in session
        import time
        session = self.client.session
        session['authorized_previews'] = {str(doc.pk): time.time()}
        session.save()
        response = self.client.get(reverse('documents:signature_preview', args=[doc.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/png')
        self.assertIn('inline', response['Content-Disposition'])
        
        # 3. Other user cannot access signature preview even if authorized in their own session
        self.client.force_login(self.other_user)
        session = self.client.session
        session['authorized_previews'] = {str(doc.pk): time.time()}
        session.save()
        response = self.client.get(reverse('documents:signature_preview', args=[doc.pk]))
        self.assertEqual(response.status_code, 403)

    def test_ajax_validate_signature(self):
        # Create a document for owner without signature
        doc = Document.objects.create(
            owner=self.owner,
            title="AJAX Document",
            file=SimpleUploadedFile("test.png", b"png_data", content_type="image/png"),
            content_type="image/png"
        )
        
        # 1. Non-owner cannot validate signature (Broken Access Control)
        self.client.force_login(self.other_user)
        response = self.client.post(
            reverse('documents:validate_signature', args=[doc.pk]),
            data='{"signature_data": "' + self.dummy_sig_base64 + '"}',
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 403)
        
        # 2. Owner can validate signature via AJAX POST
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('documents:validate_signature', args=[doc.pk]),
            data='{"signature_data": "' + self.dummy_sig_base64 + '"}',
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        
        # Verify JSON response contains success status and preview links
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertIn('preview_url', data)
        self.assertIn('signature_url', data)
        
        # Verify DB updated
        doc.refresh_from_db()
        self.assertIsNotNone(doc.signature_image)
        self.assertTrue(doc.signature_image.name.startswith('signatures/sig_'))
