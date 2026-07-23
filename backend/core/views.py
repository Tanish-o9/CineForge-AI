from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
import httpx
import os
import logging

from .models import Movie, RenderJob
from .serializers import MovieListSerializer, MovieDetailSerializer, RenderJobSerializer

logger = logging.getLogger(__name__)
FASTAPI_URL = os.environ.get('FASTAPI_URL', 'http://fastapi:8001')

class MovieViewSet(viewsets.ModelViewSet):
    queryset = Movie.objects.all().order_by('-created_at')

    def get_serializer_class(self):
        if self.action == 'list':
            return MovieListSerializer
        return MovieDetailSerializer

    def perform_create(self, serializer):
        movie = serializer.save()
        # Automatically trigger pipeline run
        self._trigger_pipeline(movie.id)

    @action(detail=True, methods=['post'], url_path='generate')
    def trigger_generation(self, request, pk=None):
        movie = self.get_object()
        success = self._trigger_pipeline(movie.id)
        if success:
            return Response({'status': 'Pipeline triggered successfully'}, status=status.HTTP_200_OK)
        return Response({'error': 'Failed to trigger FastAPI pipeline'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _trigger_pipeline(self, movie_id):
        try:
            logger.info(f"Triggering FastAPI pipeline for movie ID: {movie_id}")
            # Non-blocking or async trigger: call FastAPI pipeline endpoint
            response = httpx.post(f"{FASTAPI_URL}/api/pipeline/generate", json={"movie_id": movie_id}, timeout=5.0)
            if response.status_code == 200 or response.status_code == 202:
                logger.info(f"Successfully triggered pipeline for movie {movie_id}")
                return True
            else:
                logger.error(f"FastAPI pipeline trigger returned status {response.status_code}: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error calling FastAPI pipeline: {str(e)}")
            # Even if FastAPI service is temporarily offline, we don't block Django creation
            return False

class RenderJobViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = RenderJob.objects.all().order_by('-created_at')
    serializer_class = RenderJobSerializer
    lookup_field = 'job_id'
