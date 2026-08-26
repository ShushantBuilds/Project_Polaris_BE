from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import Tag, ContentItem, UserProfile, Interaction
from .recommendations import get_recommendations, WEIGHTS

User = get_user_model()


class UserProfileSignalTests(TestCase):
    """Confirms every new user automatically gets a UserProfile, which the algorithm depends on."""

    def test_profile_is_auto_created_on_registration(self):
        user = User.objects.create_user(email='newuser@example.com', password='pass12345')
        self.assertTrue(UserProfile.objects.filter(user=user).exists())


class RecommendationAlgorithmTests(TestCase):
    def setUp(self):
        self.tag_django = Tag.objects.create(name='Django', category='GENRE')
        self.tag_react = Tag.objects.create(name='React', category='GENRE')
        self.tag_beginner = Tag.objects.create(name='Beginner', category='DIFFICULTY')

        self.item_django = ContentItem.objects.create(title='Django Basics', description='Intro to Django')
        self.item_django.tags.add(self.tag_django)

        self.item_django_beginner = ContentItem.objects.create(title='Django for Beginners', description='...')
        self.item_django_beginner.tags.add(self.tag_django, self.tag_beginner)

        self.item_react = ContentItem.objects.create(title='React Basics', description='Intro to React')
        self.item_react.tags.add(self.tag_react)

        self.item_react_advanced = ContentItem.objects.create(title='Advanced React Patterns', description='...')
        self.item_react_advanced.tags.add(self.tag_react)

        self.item_unrelated = ContentItem.objects.create(title='Cooking Tips', description='Nothing to do with code')

        self.user = User.objects.create_user(email='test@example.com', password='testpass123')
        self.profile = self.user.profile  # auto-created by the signal above

    def test_true_cold_start_returns_results_without_error(self):
        """A brand-new user with no onboarding tags and no interactions should still get non-empty recommendations."""
        recs = get_recommendations(self.user)
        self.assertGreater(len(recs), 0)

    def test_explicit_preferences_rank_matching_items_higher(self):
        """Items sharing an onboarding-selected tag should rank above unrelated items."""
        self.profile.explicit_preferences.add(self.tag_django)
        recs = get_recommendations(self.user)
        titles = [r['item'].title for r in recs]
        self.assertLess(titles.index(self.item_django.title), titles.index(self.item_unrelated.title))
        self.assertLess(titles.index(self.item_django_beginner.title), titles.index(self.item_unrelated.title))

    def test_seen_items_are_excluded(self):
        """Once a user interacts with an item, it should never be recommended again."""
        Interaction.objects.create(user=self.user, content_item=self.item_django, interaction_type='CLICK')
        recs = get_recommendations(self.user)
        self.assertNotIn(self.item_django.id, [r['item'].id for r in recs])

    def test_interactions_boost_related_but_unseen_content(self):
        """Liking one item should raise other items sharing its tags, even with zero onboarding preferences."""
        Interaction.objects.create(user=self.user, content_item=self.item_react, interaction_type='LIKE')
        recs = get_recommendations(self.user)
        titles = [r['item'].title for r in recs]
        self.assertLess(titles.index(self.item_react_advanced.title), titles.index(self.item_unrelated.title))

    def test_explicit_and_inferred_signals_combine(self):
        """A user with both onboarding tags and click history should get results reflecting both signals."""
        self.profile.explicit_preferences.add(self.tag_beginner)
        Interaction.objects.create(user=self.user, content_item=self.item_react, interaction_type='LIKE')
        recs = get_recommendations(self.user)
        titles = [r['item'].title for r in recs]
        self.assertLess(titles.index(self.item_django_beginner.title), titles.index(self.item_unrelated.title))
        self.assertLess(titles.index(self.item_react_advanced.title), titles.index(self.item_unrelated.title))

    def test_interaction_weights_ordered_correctly(self):
        """Regression guard: LIKE must count for more than CLICK, which must count for more than VIEW."""
        self.assertGreater(WEIGHTS['LIKE'], WEIGHTS['CLICK'])
        self.assertGreater(WEIGHTS['CLICK'], WEIGHTS['VIEW'])


class InteractionScopingTests(TestCase):
    """Confirms interactions are properly isolated per user."""

    def setUp(self):
        self.tag = Tag.objects.create(name='Django', category='GENRE')
        self.item = ContentItem.objects.create(title='Django Basics', description='...')
        self.item.tags.add(self.tag)
        self.user_a = User.objects.create_user(email='a@example.com', password='pass12345')
        self.user_b = User.objects.create_user(email='b@example.com', password='pass12345')

    def test_interactions_are_scoped_to_the_owning_user(self):
        Interaction.objects.create(user=self.user_a, content_item=self.item, interaction_type='VIEW')
        self.assertEqual(Interaction.objects.filter(user=self.user_a).count(), 1)
        self.assertEqual(Interaction.objects.filter(user=self.user_b).count(), 0)