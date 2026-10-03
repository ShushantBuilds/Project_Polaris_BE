from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *

router = DefaultRouter()
router.register(r'tags', TagViewSet, basename='tag')
router.register(r'content-items', ContentItemViewSet, basename='contentitem')
router.register(r'profiles', UserProfileViewSet, basename='userprofile')
router.register(r'interactions', InteractionViewSet, basename='interaction')

urlpatterns = [
    path('', include(router.urls)),
    path('recommendations/', RecommendationView.as_view(), name='recommendations'),
    path('content-items/<int:content_item_id>/toggle/', ToggleInteractionView.as_view(), name='toggle_interaction'),
    path('content-items/<int:content_item_id>/vote/', VoteView.as_view(), name='vote_on_item'),
    path('my-library/', MyLibraryView.as_view(), name='my_library'),
    path('daily-search-suggestions/', DailySearchSuggestionsView.as_view(), name='daily_search_suggestions'),
    path('assistant/chat/', RAGAssistantView.as_view(), name='rag-chat'),
]