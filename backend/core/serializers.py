from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Movie, Scene, Character, Location, Asset, RenderJob

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']

class CharacterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Character
        fields = ['id', 'name', 'age', 'role', 'personality', 'physical_description', 'voice_id', 'reference_sheet_path']

class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ['id', 'name', 'style_prompt', 'reference_image_path']

class SceneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Scene
        fields = ['id', 'scene_number', 'location', 'time_of_day', 'description', 'emotional_beat', 'screenplay_text', 'estimated_duration', 'order_index']

class AssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = ['id', 'scene', 'character', 'asset_type', 'file_path', 'meta_data', 'created_at']

class RenderJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = RenderJob
        fields = ['id', 'job_id', 'status', 'current_stage', 'progress', 'error_message', 'created_at', 'updated_at']

class MovieDetailSerializer(serializers.ModelSerializer):
    characters = CharacterSerializer(many=True, read_only=True)
    locations = LocationSerializer(many=True, read_only=True)
    scenes = SceneSerializer(many=True, read_only=True)
    assets = AssetSerializer(many=True, read_only=True)
    jobs = RenderJobSerializer(many=True, read_only=True)

    class Meta:
        model = Movie
        fields = [
            'id', 'title', 'user_prompt', 'genre', 'tone', 'target_duration_seconds',
            'story_summary', 'screenplay_raw', 'final_video_path', 'status',
            'created_at', 'updated_at', 'characters', 'locations', 'scenes', 'assets', 'jobs'
        ]

class MovieListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Movie
        fields = ['id', 'title', 'user_prompt', 'status', 'created_at', 'updated_at']
