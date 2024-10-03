from django.db import models

class MergeTask(models.Model):
    task_id = models.CharField(max_length=255)
    status = models.CharField(max_length=20, default='processing')
    short_video_path = models.JSONField(null=True, blank=True)
    large_video_paths = models.JSONField(null=True, blank=True)
    video_links = models.JSONField(null=True, blank=True)

    def __str__(self) -> str:
        return self.status
