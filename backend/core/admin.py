from django.contrib import admin
from .models import Movie, Character, Location, Scene, Asset, RenderJob

@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'genre', 'target_duration_seconds', 'created_at')
    list_filter = ('status', 'genre')
    search_fields = ('title', 'user_prompt')

@admin.register(Character)
class CharacterAdmin(admin.ModelAdmin):
    list_display = ('name', 'movie', 'role', 'voice_id')
    search_fields = ('name', 'role')

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'movie')
    search_fields = ('name',)

@admin.register(Scene)
class SceneAdmin(admin.ModelAdmin):
    list_display = ('scene_number', 'movie', 'location', 'time_of_day', 'estimated_duration')
    list_filter = ('time_of_day',)
    ordering = ('movie', 'scene_number')

@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ('asset_type', 'movie', 'scene', 'character', 'created_at')
    list_filter = ('asset_type',)

@admin.register(RenderJob)
class RenderJobAdmin(admin.ModelAdmin):
    list_display = ('job_id', 'movie', 'status', 'current_stage', 'progress', 'created_at')
    list_filter = ('status', 'current_stage')
