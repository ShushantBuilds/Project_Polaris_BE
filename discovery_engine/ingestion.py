import requests
from django.conf import settings
from django.db.models import Count
from .models import Tag, ContentItem
from .embeddings import compute_embedding

OPENALEX_BASE_URL = "https://api.openalex.org/works"
CONTACT_EMAIL = settings.OPENALEX_CONTACT_EMAIL


def reconstruct_abstract(inverted_index):
    if not inverted_index:
        return ""
    position_map = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            position_map[pos] = word
    return " ".join(position_map[i] for i in sorted(position_map))


def _make_room(needed_slots):
    """Evicts zero-engagement items, oldest first, to stay under MAX_CONTENT_ITEMS."""
    overflow = (ContentItem.objects.count() + needed_slots) - settings.MAX_CONTENT_ITEMS
    if overflow <= 0:
        return
    evictable_ids = (ContentItem.objects
                      .annotate(interaction_count=Count('interactions'))
                      .filter(interaction_count=0, upvotes=0, downvotes=0)
                      .order_by('created_at')
                      .values_list('id', flat=True)[:overflow])
    ContentItem.objects.filter(id__in=list(evictable_ids)).delete()


def fetch_and_ingest(query_text, per_page=10, sort_by_recency=True, tag_with_query=False):
    """tag_with_query=True: only for the scheduled broad-field seed job (adds one clean category
    tag like 'Computer Science'). Live search leaves this False — tagging relies entirely on each
    paper's own OpenAlex concepts, so no raw search phrase ever becomes a tag."""
    _make_room(per_page)

    seed_tag = None
    if tag_with_query:
        seed_tag, _ = Tag.objects.get_or_create(name=query_text, category='GENRE')

    params = {'search': query_text, 'per_page': per_page, 'mailto': CONTACT_EMAIL}
    if sort_by_recency:
        params['sort'] = 'publication_date:desc'

    try:
        response = requests.get(OPENALEX_BASE_URL, params=params, timeout=15)
        response.raise_for_status()
    except requests.RequestException:
        return 0

    added = 0
    for work in response.json().get('results', []):
        external_id = work.get('id')
        if not external_id or ContentItem.objects.filter(external_id=external_id).exists():
            continue

        title = (work.get('title') or 'Untitled')[:500]
        abstract = reconstruct_abstract(work.get('abstract_inverted_index'))
        url = (work.get('primary_location') or {}).get('landing_page_url') or work.get('doi') or ''

        item = ContentItem.objects.create(
            title=title,
            description=abstract[:2000] if abstract else 'No abstract available.',
            url=url,
            external_id=external_id,
        )
        item.embedding = compute_embedding(f"{title}. {abstract}")
        item.save(update_fields=['embedding'])

        if seed_tag:
            item.tags.add(seed_tag)

        top_concepts = sorted(work.get('concepts', []), key=lambda c: c.get('score', 0), reverse=True)[:3]
        for concept in top_concepts:
            concept_name = concept.get('display_name', '').strip()
            if concept_name:
                tag = Tag.objects.filter(name__iexact=concept_name, category='GENRE').first() \
                      or Tag.objects.create(name=concept_name, category='GENRE')
                item.tags.add(tag)

        added += 1
    return added