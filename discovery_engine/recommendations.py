from collections import Counter
from django.db.models import Count, Max, F
from .models import ContentItem, Interaction
from .embeddings import cosine_similarity
import numpy as np

EMBEDDING_WEIGHT = 2.0
WEIGHTS = {'VIEW': 1, 'CLICK': 2, 'LIKE': 3}
EXPLICIT_WEIGHT = 3

def _get_user_embedding(interactions):
    weighted_vectors = []
    strong_types = {'LIKE': 3, 'SAVE': 3, 'UPVOTE': 2}
    for interaction in interactions:
        weight = strong_types.get(interaction.interaction_type)
        if weight and interaction.content_item.embedding:
            weighted_vectors.append((np.array(interaction.content_item.embedding), weight))
    if not weighted_vectors:
        return None
    total_weight = sum(w for _, w in weighted_vectors)
    combined = sum(vec * w for vec, w in weighted_vectors) / total_weight
    norm = np.linalg.norm(combined)
    return (combined / norm).tolist() if norm > 0 else None


def get_recommendations(user, limit=10):
    profile = user.profile
    explicit_tag_ids = set(profile.explicit_preferences.values_list('id', flat=True))

    interactions = Interaction.objects.filter(user=user).select_related('content_item').prefetch_related('content_item__tags')

    inferred_counts = Counter()
    for interaction in interactions:
        weight = WEIGHTS.get(interaction.interaction_type, 1)
        for tag_id in interaction.content_item.tags.values_list('id', flat=True):
            inferred_counts[tag_id] += weight

    tag_scores = {tid: EXPLICIT_WEIGHT for tid in explicit_tag_ids}
    for tag_id, count in inferred_counts.items():
        tag_scores[tag_id] = tag_scores.get(tag_id, 0) + count

    seen_ids = interactions.values_list('content_item_id', flat=True)

    # Tier 1: true cold start — popularity fallback, normalized into a 0–1 confidence range
    if not tag_scores:
        items = list(
            ContentItem.objects.exclude(id__in=seen_ids)
            .annotate(pop=Count('interactions'), net_votes=F('upvotes') - F('downvotes'))
            .order_by('-net_votes', '-pop', '-created_at')[:limit]
        )
        max_pop = max((i.pop for i in items), default=0)
        return [{'item': item, 'score': (item.pop / max_pop) if max_pop else 0.3} for item in items]

    # Tiers 2 & 3: weighted tag-overlap scoring
    user_embedding = _get_user_embedding(interactions)
    candidates = ContentItem.objects.exclude(id__in=seen_ids).prefetch_related('tags')
    scored = []
    for item in candidates:
        tag_score = sum(tag_scores.get(t.id, 0) for t in item.tags.all())
        semantic_score = cosine_similarity(user_embedding, item.embedding) * EMBEDDING_WEIGHT if (user_embedding and item.embedding) else 0
        combined_score = tag_score + semantic_score
        if combined_score > 0:
            net_votes = item.upvotes - item.downvotes
            vote_multiplier = max(1 + (net_votes * 0.05), 0.1)
            scored.append((combined_score * vote_multiplier, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)

    if len(results) < limit:
        used_ids = {r['item'].id for r in results}
        filler = (ContentItem.objects.exclude(id__in=seen_ids).exclude(id__in=used_ids)
                  .annotate(pop=Count('interactions')).order_by('-pop')[:limit - len(results)])
        results += [{'item': item, 'score': 0.25} for item in filler]
    return results

def _recycle_seen_items(user, limit):
    last_seen = (Interaction.objects.filter(user=user)
                 .values('content_item')
                 .annotate(last_seen_at=Max('timestamp'))
                 .order_by('last_seen_at'))
    ordered_ids = [row['content_item'] for row in last_seen][:limit]
    items = {item.id: item for item in ContentItem.objects.filter(id__in=ordered_ids).prefetch_related('tags')}
    return [{'item': items[i], 'score': 0.2} for i in ordered_ids if i in items]