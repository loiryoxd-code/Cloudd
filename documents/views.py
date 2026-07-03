from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.http import FileResponse, HttpResponseRedirect, Http404
from django.conf import settings

import os
from .models import Document
from .forms import SecureDocumentForm
from core.utils import log_security_event

# 1. List Documents (A01:2021 - Broken Access Control Prevention)
@login_required
def document_list(request):
    # Retrieve only the documents owned by the logged-in user
    documents = Document.objects.filter(owner=request.user)
    return render(request, 'documents/list.html', {'documents': documents})

# 2. Detail Document (A01:2021 Check)
@login_required
def document_detail(request, pk):
    # Fetch document or raise 404
    document = get_object_or_404(Document, pk=pk)
    
    # Restrict viewing strictly to the owner
    if document.owner != request.user:
        log_security_event(
            request, 
            'UNAUTHORIZED_VIEW_ATTEMPT', 
            f"El usuario '{request.user.username}' intentó ver el documento ID {pk} de '{document.owner.username}'.", 
            severity='CRITICAL'
        )
        raise PermissionDenied("No tienes autorización para ver esta evidencia.")

    # Check temporal preview authorization (valid for 120 seconds / 2 minutes)
    import time
    authorized_previews = request.session.get('authorized_previews', {})
    auth_time = authorized_previews.get(str(pk), 0)
    is_authorized = (time.time() - auth_time) < 120

    context = {
        'document': document,
        'decrypted_notes': decrypted_notes,
        'is_authorized': is_authorized,
    }
    return render(request, 'documents/detail.html', context)

# 3. Create Document (Secure Upload)
@login_required
def document_create(request):
    if request.method == 'POST':
        form = SecureDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            document = form.save(commit=False)
            document.owner = request.user
            
            # Encrypt sensitive notes field before saving to Database (A02:2021)
            document.encrypt_notes(form.cleaned_data.get('notes', ''))
            
            # Save handwritten signature if drawn
            sig_data = form.cleaned_data.get('signature_data')
            if sig_data and sig_data.startswith('data:image/png;base64,'):
                import base64
                import time
                from django.core.files.base import ContentFile
                try:
                    format, imgstr = sig_data.split(';base64,')
                    data = ContentFile(base64.b64decode(imgstr), name=f"sig_{request.user.id}_{int(time.time())}.png")
                    document.signature_image = data
                except Exception:
                    pass

            document.save()
            
            # Authorize temporal preview in session if signed on upload
            if document.signature_image:
                import time
                authorized_previews = request.session.get('authorized_previews', {})
                authorized_previews[str(document.pk)] = time.time()
                request.session['authorized_previews'] = authorized_previews
                request.session.modified = True
            
            log_security_event(
                request, 
                'DOCUMENT_UPLOAD', 
                f"El usuario '{request.user.username}' subió el documento '{document.title}' (Hash SHA-256: {document.file_hash})."
            )
            messages.success(request, f"Documento '{document.title}' subido correctamente.")
            return redirect('documents:detail', pk=document.pk)
        else:
            messages.error(request, "Error al subir el documento. Revisa los campos.")
    else:
        form = SecureDocumentForm()
        
    return render(request, 'documents/form.html', {'form': form, 'title': 'Subir Nueva Evidencia'})

# 4. Update Document
@login_required
def document_update(request, pk):
    document = get_object_or_404(Document, pk=pk)
    
    # Ownership Check
    if document.owner != request.user:
        log_security_event(
            request, 
            'UNAUTHORIZED_EDIT_ATTEMPT', 
            f"El usuario '{request.user.username}' intentó editar el documento ID {pk} de '{document.owner.username}'.", 
            severity='CRITICAL'
        )
        raise PermissionDenied("No tienes autorización para modificar esta evidencia.")

    if request.method == 'POST':
        form = SecureDocumentForm(request.POST, request.FILES, instance=document)
        if form.is_valid():
            updated_doc = form.save(commit=False)
            updated_doc.encrypt_notes(form.cleaned_data.get('notes', ''))
            
            # Save handwritten signature if new signature drawn
            sig_data = form.cleaned_data.get('signature_data')
            if sig_data and sig_data.startswith('data:image/png;base64,'):
                import base64
                import time
                from django.core.files.base import ContentFile
                try:
                    # Delete old signature file if exists and using local FileSystemStorage
                    if updated_doc.signature_image and settings.DEFAULT_FILE_STORAGE == 'django.core.files.storage.FileSystemStorage':
                        try:
                            if os.path.exists(updated_doc.signature_image.path):
                                os.remove(updated_doc.signature_image.path)
                        except Exception:
                            pass
                    
                    format, imgstr = sig_data.split(';base64,')
                    data = ContentFile(base64.b64decode(imgstr), name=f"sig_{request.user.id}_{int(time.time())}.png")
                    updated_doc.signature_image = data
                except Exception:
                    pass

            updated_doc.save()
            
            # Authorize temporal preview in session if signed on update
            if updated_doc.signature_image:
                import time
                authorized_previews = request.session.get('authorized_previews', {})
                authorized_previews[str(updated_doc.pk)] = time.time()
                request.session['authorized_previews'] = authorized_previews
                request.session.modified = True
            
            log_security_event(
                request, 
                'DOCUMENT_UPDATE', 
                f"El usuario '{request.user.username}' modificó el documento '{updated_doc.title}'."
            )
            messages.success(request, f"Documento '{updated_doc.title}' actualizado.")
            return redirect('documents:detail', pk=updated_doc.pk)
    else:
        # Decrypt notes to prefill the form field
        decrypted_notes = document.decrypt_notes()
        form = SecureDocumentForm(instance=document, initial={'notes': decrypted_notes})

    return render(request, 'documents/form.html', {'form': form, 'title': 'Editar Evidencia', 'is_edit': True, 'document': document})

# 5. Delete Document
@login_required
def document_delete(request, pk):
    document = get_object_or_404(Document, pk=pk)
    
    # Ownership Check
    if document.owner != request.user:
        log_security_event(
            request, 
            'UNAUTHORIZED_DELETE_ATTEMPT', 
            f"El usuario '{request.user.username}' intentó borrar el documento ID {pk} de '{document.owner.username}'.", 
            severity='CRITICAL'
        )
        raise PermissionDenied("No tienes autorización para borrar esta evidencia.")

    if request.method == 'POST':
        title = document.title
        file_path = document.file.name
        
        # In case of local storage, clean up physical file to prevent leftover files
        if settings.DEFAULT_FILE_STORAGE == 'django.core.files.storage.FileSystemStorage':
            try:
                if document.file and os.path.exists(document.file.path):
                    os.remove(document.file.path)
            except Exception as e:
                log_security_event(request, 'FILE_DELETE_ERROR', f"Error eliminando archivo físico: {str(e)}", severity='WARNING')

        # Clean up signature image if exists
        if document.signature_image and settings.DEFAULT_FILE_STORAGE == 'django.core.files.storage.FileSystemStorage':
            try:
                if os.path.exists(document.signature_image.path):
                    os.remove(document.signature_image.path)
            except Exception:
                pass

        document.delete()
        log_security_event(request, 'DOCUMENT_DELETE', f"El usuario '{request.user.username}' eliminó el documento '{title}' (Ruta: {file_path}).")
        messages.success(request, f"Documento '{title}' eliminado correctamente.")
        return redirect('documents:list')
        
    return render(request, 'documents/confirm_delete.html', {'document': document})

# 6. Secure Download / Access Controller (A01:2021, A04:2021)
@login_required
def document_download(request, pk):
    document = get_object_or_404(Document, pk=pk)
    
    # Prevent unauthorized downloading of other user's files
    if document.owner != request.user:
        log_security_event(
            request, 
            'UNAUTHORIZED_DOWNLOAD_ATTEMPT', 
            f"El usuario '{request.user.username}' intentó descargar el archivo ID {pk} perteneciente a '{document.owner.username}'.", 
            severity='CRITICAL'
        )
        raise PermissionDenied("Acceso denegado a este recurso.")

    log_security_event(
        request, 
        'DOCUMENT_DOWNLOAD', 
        f"El usuario '{request.user.username}' descargó el archivo '{document.file.name}'."
    )

    # If Azure Blob Storage is active, generate short-lived SAS URL or stream
    if settings.DEFAULT_FILE_STORAGE == 'storages.backends.azure_storage.AzureStorage':
        try:
            # django-storages automatically generates temporary signed URLs for private container files
            url = document.file.url
            return HttpResponseRedirect(url)
        except Exception as e:
            log_security_event(request, 'AZURE_STORAGE_ERROR', f"Error generando URL firmada para Azure: {str(e)}", severity='WARNING')
            raise Http404("Error al recuperar el archivo del almacenamiento en la nube.")
    else:
        # Local Storage File Streaming (Securely hiding local file system paths)
        try:
            response = FileResponse(document.file.open('rb'), content_type=document.content_type)
            # Instruct browser to download the file instead of displaying inline
            response['Content-Disposition'] = f'attachment; filename="{os.path.basename(document.file.name)}"'
            return response
        except FileNotFoundError:
            raise Http404("El archivo físico no fue encontrado en el servidor.")

# 7. Secure Preview / Access Controller (A01:2021, A04:2021)
@login_required
def document_preview(request, pk):
    document = get_object_or_404(Document, pk=pk)
    
    # Prevent unauthorized previewing of other user's files
    if document.owner != request.user:
        log_security_event(
            request, 
            'UNAUTHORIZED_PREVIEW_ATTEMPT', 
            f"El usuario '{request.user.username}' intentó previsualizar el archivo ID {pk} perteneciente a '{document.owner.username}'.", 
            severity='CRITICAL'
        )
        raise PermissionDenied("Acceso denegado a este recurso.")

    # Prevent previewing if document is not signed/validated (OWASP A04:2021 Safe-by-default)
    if not document.signature_image:
        log_security_event(
            request, 
            'UNAUTHORIZED_PREVIEW_UNSIGNED', 
            f"El usuario '{request.user.username}' intentó previsualizar el archivo ID {pk} sin estar firmado/validado.", 
            severity='WARNING'
        )
        raise PermissionDenied("Evidencia protegida pendiente de validación.")

    # Check temporal preview authorization (valid for 120 seconds / 2 minutes)
    import time
    authorized_previews = request.session.get('authorized_previews', {})
    auth_time = authorized_previews.get(str(pk), 0)
    if (time.time() - auth_time) >= 120:
        log_security_event(
            request, 
            'UNAUTHORIZED_PREVIEW_EXPIRED', 
            f"El usuario '{request.user.username}' intentó previsualizar el archivo ID {pk} pero la autorización temporal expiró.", 
            severity='WARNING'
        )
        raise PermissionDenied("Autorización temporal expirada. Debe firmar nuevamente para ver la evidencia.")

    log_security_event(
        request, 
        'DOCUMENT_PREVIEW', 
        f"El usuario '{request.user.username}' previsualizó el archivo '{document.file.name}'."
    )

    try:
        file_obj = document.file.open('rb')
        response = FileResponse(file_obj, content_type=document.content_type)
        response['Content-Disposition'] = f'inline; filename="{os.path.basename(document.file.name)}"'
        return response
    except Exception as e:
        log_security_event(request, 'PREVIEW_ERROR', f"Error al abrir archivo para vista previa: {str(e)}", severity='WARNING')
        raise Http404("No se pudo cargar la vista previa del archivo.")

# 8. Secure Signature Preview / Access Controller (A01:2021, A04:2021)
@login_required
def signature_preview(request, pk):
    document = get_object_or_404(Document, pk=pk)
    
    # Prevent unauthorized previewing of other user's signatures
    if document.owner != request.user:
        log_security_event(
            request, 
            'UNAUTHORIZED_SIGNATURE_PREVIEW_ATTEMPT', 
            f"El usuario '{request.user.username}' intentó previsualizar la firma del documento ID {pk} perteneciente a '{document.owner.username}'.", 
            severity='CRITICAL'
        )
        raise PermissionDenied("Acceso denegado a este recurso.")

    if not document.signature_image:
        raise Http404("No hay firma manuscrita para este documento.")

    # Check temporal preview authorization (valid for 120 seconds / 2 minutes)
    import time
    authorized_previews = request.session.get('authorized_previews', {})
    auth_time = authorized_previews.get(str(pk), 0)
    if (time.time() - auth_time) >= 120:
        raise PermissionDenied("Autorización temporal expirada. Debe firmar nuevamente.")

    try:
        file_obj = document.signature_image.open('rb')
        response = FileResponse(file_obj, content_type='image/png')
        response['Content-Disposition'] = f'inline; filename="{os.path.basename(document.signature_image.name)}"'
        return response
    except Exception as e:
        log_security_event(request, 'SIGNATURE_PREVIEW_ERROR', f"Error al abrir firma para vista previa: {str(e)}", severity='WARNING')
        raise Http404("No se pudo cargar la vista previa de la firma.")

# 9. AJAX Validate Signature and Save (OWASP A01:2021)
@login_required
def document_validate_signature(request, pk):
    from django.http import JsonResponse
    from django.urls import reverse
    import json
    
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
    
    document = get_object_or_404(Document, pk=pk)
    
    if document.owner != request.user:
        log_security_event(
            request, 
            'UNAUTHORIZED_SIGNATURE_VALIDATE_ATTEMPT', 
            f"El usuario '{request.user.username}' intentó firmar/validar el documento ID {pk} perteneciente a '{document.owner.username}'.", 
            severity='CRITICAL'
        )
        return JsonResponse({'status': 'error', 'message': 'Acceso denegado'}, status=403)
        
    try:
        data = json.loads(request.body)
        sig_data = data.get('signature_data')
    except Exception:
        return JsonResponse({'status': 'error', 'message': 'Datos inválidos'}, status=400)
        
    if sig_data and sig_data.startswith('data:image/png;base64,'):
        import base64
        import time
        from django.core.files.base import ContentFile
        try:
            # Delete old signature file if exists and using local FileSystemStorage
            if document.signature_image and settings.DEFAULT_FILE_STORAGE == 'django.core.files.storage.FileSystemStorage':
                try:
                    if os.path.exists(document.signature_image.path):
                        os.remove(document.signature_image.path)
                except Exception:
                    pass
            
            format, imgstr = sig_data.split(';base64,')
            file_data = ContentFile(base64.b64decode(imgstr), name=f"sig_{request.user.id}_{int(time.time())}.png")
            document.signature_image = file_data
            document.save()
            
            # Authorize temporal preview in session for 120 seconds
            authorized_previews = request.session.get('authorized_previews', {})
            authorized_previews[str(pk)] = time.time()
            request.session['authorized_previews'] = authorized_previews
            request.session.modified = True

            log_security_event(
                request, 
                'SIGNATURE_VALIDATED', 
                f"El usuario '{request.user.username}' firmó y validó el documento '{document.title}'."
            )
            
            return JsonResponse({
                'status': 'success',
                'preview_url': reverse('documents:preview', args=[pk]),
                'signature_url': reverse('documents:signature_preview', args=[pk])
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'Error al procesar la firma: {str(e)}'}, status=500)
            
    return JsonResponse({'status': 'error', 'message': 'Firma inválida o vacía'}, status=400)
