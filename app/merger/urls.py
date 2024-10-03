from django.urls import path
from . import views


app_name = 'merger'

urlpatterns = [
    path('', views.index, name='index'),
    path('upload/', views.upload_files, name='upload_files'),
    path('processing/<str:task_id>/', views.processing, name='processing'),
    path('check_status/<str:task_id>/', views.check_task_status, name='check_status'),
    path('download_zip/<str:task_id>/', views.download_zip, name='download_zip'),
    path('download_output/<path:videopath>/', views.download_video, name='download_output'),
    path('processing_successful/<str:task_id>/', views.processing_successful, name='processing_successful'),
]
