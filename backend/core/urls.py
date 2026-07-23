from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MovieViewSet, RenderJobViewSet

router = DefaultRouter()
router.register(r'movies', MovieViewSet, basename='movie')
router.register(r'jobs', RenderJobViewSet, basename='job')

urlpatterns = [
    path('', include(router.urls)),
]
