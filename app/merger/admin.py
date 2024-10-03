from django.contrib import admin
from .models import MergeTask

# Register your models here.
@admin.register(MergeTask)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['task_id', 'status', 'short_video_path', 'large_video_paths','video_links']