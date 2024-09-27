from django.contrib import admin
from .models import Hook, Task

# Register your models here.
@admin.register(Hook)
class HookAdmin(admin.ModelAdmin):
    list_display = ['hooks_content', 'google_sheets_link',
                    'eleven_labs_api_key', 'voice_id']
    
@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['task_id', 'status', 'video_links']