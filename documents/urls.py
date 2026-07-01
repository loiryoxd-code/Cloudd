from django.urls import path
from . import views

app_name = 'documents'

urlpatterns = [
    path('', views.document_list, name='list'),
    path('upload/', views.document_create, name='create'),
    path('<int:pk>/', views.document_detail, name='detail'),
    path('<int:pk>/edit/', views.document_update, name='update'),
    path('<int:pk>/delete/', views.document_delete, name='delete'),
    path('<int:pk>/download/', views.document_download, name='download'),
]
