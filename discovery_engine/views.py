from rest_framework.throttling import ScopedRateThrottle
from django.contrib.postgres.search import SearchQuery, SearchRank
from pgvector.django import CosineDistance
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import viewsets, permissions
from .pagination import StandardResultsSetPagination
from .models import Tag, ContentItem, UserProfile, Interaction
from .serializers import TagSerializer, ContentItemSerializer, UserProfileSerializer, InteractionSerializer
from .recommendations import get_recommendations
from django.db.models import F, Case, When, Count
from django.db import transaction
from .embeddings import compute_embedding
from .ingestion import fetch_and_ingest
import random
from datetime import date

class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [permissions.IsAuthenticated]

# class ContentItemViewSet(viewsets.ModelViewSet):
#     queryset = ContentItem.objects.all()
#     serializer_class = ContentItemSerializer
#     permission_classes = [permissions.IsAuthenticated]

class UserProfileViewSet(viewsets.ModelViewSet):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UserProfile.objects.filter(user=self.request.user)

class InteractionViewSet(viewsets.ModelViewSet):
    serializer_class = InteractionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Interaction.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)  # frontend never sends user_id directly


class RecommendationView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        recs = get_recommendations(request.user)
        data = [
            {**ContentItemSerializer(r['item']).data, 'confidence_score': r['score']}
            for r in recs
        ]
        return Response(data)


class ContentItemViewSet(viewsets.ModelViewSet):
    serializer_class = ContentItemSerializer
    pagination_class = StandardResultsSetPagination
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'ai_search'

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        queryset = ContentItem.objects.all()
        q = self.request.query_params.get('search')
        if not q:
            return queryset

        query = SearchQuery(q)
        keyword_results = queryset.filter(search_vector=query).annotate(rank=SearchRank('search_vector', query)).order_by('-rank')
        if keyword_results.exists():
            return keyword_results

        semantic_results = self._semantic_search(q)
        if semantic_results.exists():
            return semantic_results

        fetch_and_ingest(q, per_page=10, sort_by_recency=False)  # nothing local at all — fetch live, cache permanently
        return self._semantic_search(q)

    def _semantic_search(self, query_text, limit=20, max_distance=0.75):
        query_vector = compute_embedding(query_text)
        
        results = (
            ContentItem.objects
            .exclude(embedding__isnull=True)
            .annotate(distance=CosineDistance('embedding', query_vector))
            .filter(distance__lte=max_distance)
            .order_by('distance')
        )
        return results


class ToggleInteractionView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    TOGGLEABLE_TYPES = {'LIKE', 'SAVE'}

    def post(self, request, content_item_id):
        interaction_type = request.data.get('interaction_type')
        if interaction_type not in self.TOGGLEABLE_TYPES:
            return Response({'error': 'Invalid interaction_type.'}, status=400)
        try:
            item = ContentItem.objects.get(id=content_item_id)
        except ContentItem.DoesNotExist:
            return Response({'error': 'Not found.'}, status=404)

        existing = Interaction.objects.filter(user=request.user, content_item=item, interaction_type=interaction_type).first()
        if existing:
            existing.delete()
            return Response({'active': False})
        Interaction.objects.create(user=request.user, content_item=item, interaction_type=interaction_type)
        return Response({'active': True})


class VoteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, content_item_id):
        vote_type = request.data.get('vote_type')
        if vote_type not in ('UPVOTE', 'DOWNVOTE'):
            return Response({'error': 'vote_type must be UPVOTE or DOWNVOTE.'}, status=400)
        try:
            item = ContentItem.objects.get(id=content_item_id)
        except ContentItem.DoesNotExist:
            return Response({'error': 'Not found.'}, status=404)

        with transaction.atomic():
            existing = Interaction.objects.filter(
                user=request.user, content_item=item, interaction_type__in=['UPVOTE', 'DOWNVOTE']
            ).first()

            if existing and existing.interaction_type == vote_type:
                existing.delete()
                field = 'upvotes' if vote_type == 'UPVOTE' else 'downvotes'
                ContentItem.objects.filter(id=item.id).update(**{field: F(field) - 1})
                user_vote = None
            elif existing:
                old_field = 'upvotes' if existing.interaction_type == 'UPVOTE' else 'downvotes'
                new_field = 'upvotes' if vote_type == 'UPVOTE' else 'downvotes'
                ContentItem.objects.filter(id=item.id).update(**{old_field: F(old_field) - 1, new_field: F(new_field) + 1})
                existing.interaction_type = vote_type
                existing.save()
                user_vote = vote_type
            else:
                Interaction.objects.create(user=request.user, content_item=item, interaction_type=vote_type)
                field = 'upvotes' if vote_type == 'UPVOTE' else 'downvotes'
                ContentItem.objects.filter(id=item.id).update(**{field: F(field) + 1})
                user_vote = vote_type

        item.refresh_from_db()
        return Response({'upvotes': item.upvotes, 'downvotes': item.downvotes, 'user_vote': user_vote})


class MyLibraryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        liked_ids = Interaction.objects.filter(user=request.user, interaction_type='LIKE').values_list('content_item_id', flat=True)
        saved_ids = Interaction.objects.filter(user=request.user, interaction_type='SAVE').values_list('content_item_id', flat=True)
        context = {'request': request}
        return Response({
            'liked': ContentItemSerializer(ContentItem.objects.filter(id__in=liked_ids), many=True, context=context).data,
            'saved': ContentItemSerializer(ContentItem.objects.filter(id__in=saved_ids), many=True, context=context).data,
        })

class DailySearchSuggestionsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        eligible_tags = list(
            Tag.objects.filter(category='GENRE')
            .annotate(item_count=Count('content_items'))
            .filter(item_count__gte=3)
            .values_list('name', flat=True)
        )
        
        if not eligible_tags:
            return Response([])

        rng = random.Random(date.today().isoformat()) 
        count = min(4, len(eligible_tags))
        
        return Response(rng.sample(eligible_tags, count))