from django.db import models
from django.contrib.auth.models import User
import uuid

# If pgvector is installed, we can use VectorField. We import it.
# To handle local testing environments without postgres (optional fallback),
# we wrap it or just use it. Since postgres+pgvector is the planned environment, we use it directly.
try:
    from pgvector.django import VectorField
except ImportError:
    # Fallback for environments compiling without pgvector
    class VectorField(models.BinaryField):
        def __init__(self, dimensions=None, *args, **kwargs):
            super().__init__(*args, **kwargs)

class Movie(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed')
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='movies', null=True, blank=True)
    title = models.CharField(max_length=255, default='Untitled Movie')
    user_prompt = models.TextField()
    genre = models.CharField(max_length=100, blank=True, null=True)
    tone = models.CharField(max_length=100, blank=True, null=True)
    target_duration_seconds = models.IntegerField(default=60)
    story_summary = models.TextField(blank=True, null=True)
    screenplay_raw = models.TextField(blank=True, null=True)
    final_video_path = models.CharField(max_length=512, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.status})"

class Character(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='characters')
    name = models.CharField(max_length=100)
    age = models.CharField(max_length=50, blank=True, null=True)
    role = models.CharField(max_length=100, blank=True, null=True)
    personality = models.TextField(blank=True, null=True)
    physical_description = models.TextField(blank=True, null=True)
    voice_id = models.CharField(max_length=100, blank=True, null=True)
    reference_sheet_path = models.CharField(max_length=512, blank=True, null=True)
    # 512-dimension embedding for visual reference consistency (CLIP embedding)
    embedding = VectorField(dimensions=512, null=True, blank=True)

    def __str__(self):
        return f"{self.name} in {self.movie.title}"

class Location(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='locations')
    name = models.CharField(max_length=255)
    style_prompt = models.TextField(blank=True, null=True)
    reference_image_path = models.CharField(max_length=512, blank=True, null=True)
    # 512-dimension embedding for environmental style consistency
    embedding = VectorField(dimensions=512, null=True, blank=True)

    def __str__(self):
        return f"{self.name} in {self.movie.title}"

class Scene(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='scenes')
    scene_number = models.IntegerField()
    location = models.CharField(max_length=255)
    time_of_day = models.CharField(max_length=100)
    description = models.TextField()
    emotional_beat = models.CharField(max_length=255, blank=True, null=True)
    screenplay_text = models.TextField(blank=True, null=True) # formatted action and dialogue
    estimated_duration = models.IntegerField(default=10) # in seconds
    order_index = models.IntegerField(default=0)

    class Meta:
        ordering = ['scene_number']

    def __str__(self):
        return f"Scene {self.scene_number}: {self.location} ({self.movie.title})"

class Asset(models.Model):
    ASSET_TYPE_CHOICES = [
        ('IMAGE', 'Storyboard Image'),
        ('VOICE', 'Dialogue Voice Audio'),
        ('MUSIC', 'Background Music Track'),
        ('SFX', 'Sound Effect Clip'),
        ('VIDEO', 'Video Clip')
    ]
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='assets')
    scene = models.ForeignKey(Scene, on_delete=models.CASCADE, related_name='assets', null=True, blank=True)
    character = models.ForeignKey(Character, on_delete=models.SET_NULL, related_name='assets', null=True, blank=True)
    asset_type = models.CharField(max_length=20, choices=ASSET_TYPE_CHOICES)
    file_path = models.CharField(max_length=512)
    meta_data = models.JSONField(default=dict, blank=True) # for durations, cue timestamps, shot parameters, etc.
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.asset_type} for {self.movie.title}"

class RenderJob(models.Model):
    STAGE_CHOICES = [
        ('story', 'Story Generation'),
        ('screenplay', 'Screenplay Writing'),
        ('storyboard', 'Storyboard Planning'),
        ('character_gen', 'Character Rendering'),
        ('environment_gen', 'Environment Generation'),
        ('voice_gen', 'Voice Synthesis'),
        ('music_gen', 'Music Composition'),
        ('sfx_gen', 'Sound FX Compilation'),
        ('animation', 'Ken Burns Animation'),
        ('video_edit', 'Video Assembly'),
        ('subtitle_gen', 'ASR Subtitle Synthesis'),
        ('export', 'Final Video Export')
    ]
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='jobs')
    job_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(max_length=20, choices=Movie.STATUS_CHOICES, default='PENDING')
    current_stage = models.CharField(max_length=50, choices=STAGE_CHOICES, blank=True, null=True)
    progress = models.IntegerField(default=0) # 0 to 100
    state_data = models.JSONField(default=dict, blank=True) # full checkpoint state
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Job {self.job_id} - {self.status} (Stage: {self.current_stage})"
