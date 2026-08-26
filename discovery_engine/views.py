from django.contrib.postgres.search import SearchQuery, SearchRank
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import viewsets, permissions
from .models import Tag, ContentItem, UserProfile, Interaction
from .serializers import TagSerializer, ContentItemSerializer, UserProfileSerializer, InteractionSerializer
from .recommendations import get_recommendations
from django.db.models import F
from django.db import transaction

class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [permissions.IsAuthenticated]

class ContentItemViewSet(viewsets.ModelViewSet):
    queryset = ContentItem.objects.all()
    serializer_class = ContentItemSerializer
    permission_classes = [permissions.IsAuthenticated]

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
    queryset = ContentItem.objects.all()
    serializer_class = ContentItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = ContentItem.objects.all()
        q = self.request.query_params.get('search')
        if q:
            query = SearchQuery(q)
            queryset = queryset.filter(search_vector=query).annotate(rank=SearchRank('search_vector', query)).order_by('-rank')
        return queryset
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]


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