from rest_framework import serializers
from .models import *

class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name', 'category']


class ContentItemSerializer(serializers.ModelSerializer):
    is_liked = serializers.SerializerMethodField()
    is_saved = serializers.SerializerMethodField()
    user_vote = serializers.SerializerMethodField()

    class Meta:
        model = ContentItem
        fields = ['id', 'title', 'description', 'url', 'tags', 'upvotes', 'downvotes', 'is_liked', 'is_saved', 'user_vote', 'created_at']

    def get_is_liked(self, obj):
        user = self.context.get('request') and self.context['request'].user
        return bool(user and user.is_authenticated and Interaction.objects.filter(user=user, content_item=obj, interaction_type='LIKE').exists())

    def get_is_saved(self, obj):
        user = self.context.get('request') and self.context['request'].user
        return bool(user and user.is_authenticated and Interaction.objects.filter(user=user, content_item=obj, interaction_type='SAVE').exists())

    def get_user_vote(self, obj):
        user = self.context.get('request') and self.context['request'].user
        if not (user and user.is_authenticated):
            return None
        vote = Interaction.objects.filter(user=user, content_item=obj, interaction_type__in=['UPVOTE', 'DOWNVOTE']).first()
        return vote.interaction_type if vote else None

class UserProfileSerializer(serializers.ModelSerializer):
    explicit_preferences = TagSerializer(many=True, read_only=True)

    class Meta:
        model = UserProfile
        fields = ['id', 'user', 'onboarding_completed', 'explicit_preferences']

class InteractionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Interaction
        fields = ['id', 'content_item', 'interaction_type', 'timestamp']
        read_only_fields = ['timestamp']