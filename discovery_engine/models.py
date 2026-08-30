from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.contrib.postgres.fields import ArrayField

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)

class Tag(models.Model):
    CATEGORY_CHOICES = [
        ('GENRE', 'Genre/Topic'),
        ('FORMAT', 'Content Format'),
        ('DIFFICULTY', 'Difficulty Level'),
    ]
    name = models.CharField(max_length=50, unique=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='GENRE')
    
    def __str__(self):
        return f"{self.name} ({self.category})"


class ContentItem(models.Model):
    title = models.CharField(max_length=500)
    description = models.TextField()
    url = models.URLField(max_length=500, blank=True, null=True)
    tags = models.ManyToManyField(Tag, related_name='content_items')
    upvotes = models.PositiveIntegerField(default=0)
    downvotes = models.PositiveIntegerField(default=0)
    search_vector = SearchVectorField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    external_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    embedding = ArrayField(models.FloatField(), size=384, null=True, blank=True)
    ai_summary = models.TextField(blank=True, null=True)

    class Meta:
        # Gin Indexing
        indexes = [
            GinIndex(fields=['search_vector'], name='search_vector_idx')
        ]

    def __str__(self):
        return self.title


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    onboarding_completed = models.BooleanField(default=False)
    explicit_preferences = models.ManyToManyField(Tag, related_name='interested_users', blank=True)

    def __str__(self):
        return f"{self.user.email}'s Profile"

class Interaction(models.Model):
    INTERACTION_TYPES = [
        ('VIEW', 'View'),
        ('CLICK', 'Click'),
        ('LIKE', 'Like'),
        ('SAVE', 'Save for Later'),
        ('UPVOTE', 'Upvote'),
        ('DOWNVOTE', 'Downvote'),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='interactions')
    content_item = models.ForeignKey(ContentItem, on_delete=models.CASCADE, related_name='interactions')
    interaction_type = models.CharField(max_length=10, choices=INTERACTION_TYPES, default='CLICK')
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['user', 'timestamp'])] 