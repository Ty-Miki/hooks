from django.db import models
from django.core.exceptions import ValidationError

def validate_video_file(value):
    # List of allowed video mime types
    valid_mime_types = ['video/mp4', 'video/x-m4v', 'video/quicktime', 'video/x-msvideo', 'video/x-ms-wmv']
    file_mime_type = value.file.content_type
    
    if file_mime_type not in valid_mime_types:
        raise ValidationError(f'Unsupported file type: {file_mime_type}. Please upload a valid video file.')

class Hook(models.Model):
    hooks_content = models.FileField(max_length=500, upload_to='hooks_videos/', blank=True, null=True, validators=[validate_video_file])
    google_sheets_link = models.URLField(max_length=500, blank=True, null=True)
    eleven_labs_api_key = models.CharField(max_length=255, blank=True, null=True)
    voice_id = models.CharField(max_length=255, blank=True, null=True)
    box_color = models.CharField(max_length=7, default='#485AFF')
    font_color = models.CharField(max_length=7, default='#FFFFFF')
    task_id = models.CharField(max_length=1000, unique=True)
    parallel_processing = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.id)

class Task(models.Model):
    task_id = models.CharField(max_length=255)
    status = models.CharField(max_length=20, default='processing')
    video_links = models.JSONField(null=True, blank=True)

    def __str__(self) -> str:
        return self.status

class Package(models.Model):
    name = models.CharField(max_length=100)
    price = models.PositiveIntegerField()
    stripe_id = models.CharField(max_length=200)
    video_limit = models.PositiveIntegerField()
    price_per_video = models.FloatField(null=True, blank=True)

    def __str__(self) -> str:
        return self.name