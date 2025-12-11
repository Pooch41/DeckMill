import requests
from datetime import timedelta
from functools import reduce

from django.db.models import Q
from django.utils import timezone
from django.utils.timezone import is_naive, make_aware, get_current_timezone

from .models import CardDefinition

SCRYFALL_API_URL = "https://api.scryfall.com/cards/named"


def get_card_data(card_name):
    """
    Fetches card data with a "Scryfall Priority" for single words.

    Priority Order:
    1. Local DB Exact Match (Fast & Safe)
    2. Local DB Fuzzy Match (Only if input has multiple words)
    3. Scryfall API (The Authority for single words like "Sol")
    """
    card_name = card_name.strip()

    existing_card = CardDefinition.objects.filter(name__iexact=card_name).first()

    if existing_card:
        if _is_card_fresh(existing_card):
            print(f"✅ Exact Cache Hit: '{existing_card.name}'")
            return existing_card
        else:
            print(f"🔄 Exact Match Stale: Refreshing '{existing_card.name}'...")

    search_words = card_name.split()

    if not existing_card and len(search_words) > 1:
        query_parts = [Q(name__icontains=word) for word in search_words]
        query = reduce(lambda q1, q2: q1 & q2, query_parts)

        fuzzy_card = CardDefinition.objects.filter(query).first()

        if fuzzy_card:
            if _is_card_fresh(fuzzy_card):
                print(f"✅ Safe Fuzzy Hit: '{fuzzy_card.name}' (matched '{card_name}')")
                return fuzzy_card
            else:
                existing_card = fuzzy_card

    print(f"🌍 Querying Scryfall for '{card_name}'...")

    headers = {
        'User-Agent': 'DeckMill/1.0 (your_email@example.com)',
        'Accept': 'application/json'
    }
    params = {'fuzzy': card_name}

    try:
        response = requests.get(SCRYFALL_API_URL, params=params, headers=headers, timeout=5)

        if response.status_code == 404:
            print(f"❌ Scryfall 404: Could not find '{card_name}'")
            return None

        response.raise_for_status()
        data = response.json()

        img_front = data.get('image_uris', {}).get('normal')
        img_back = None
        mana_cost = data.get('mana_cost')
        type_line = data.get('type_line')

        if 'card_faces' in data:
            faces = data.get('card_faces', [])
            if len(faces) > 0:
                if not img_front:
                    img_front = faces[0].get('image_uris', {}).get('normal')
                if not mana_cost:
                    costs = [f.get('mana_cost') for f in faces if f.get('mana_cost')]
                    mana_cost = " // ".join(costs)
                if not type_line:
                    types = [f.get('type_line') for f in faces if f.get('type_line')]
                    type_line = " // ".join(types)
            if len(faces) > 1:
                img_back = faces[1].get('image_uris', {}).get('normal')

        card, created = CardDefinition.objects.update_or_create(
            scryfall_id=data.get('id'),
            defaults={
                'name': data.get('name'),
                'image_url': img_front,
                'image_url_back': img_back,
                'mana_cost': mana_cost,
                'type_line': type_line,
                'current_eur': data.get('prices', {}).get('eur'),
                'last_updated': timezone.now()
            }
        )

        action = "Created" if created else "Updated"
        print(f"💾 {action} '{card.name}' [Mana: {mana_cost}]")
        return card

    except requests.RequestException as e:
        print(f"⚠️ Network Error: {e}")
        if existing_card:
            return existing_card
        return None


def _is_card_fresh(card):
    """
    Helper to determine if a card needs refreshing.
    Returns True if fresh, False if stale.
    """
    last_updated = card.last_updated
    if is_naive(last_updated):
        last_updated = make_aware(last_updated, timezone=get_current_timezone())

    age = timezone.now() - last_updated

    if card.current_eur is None:
        print(f"💰 Price missing for '{card.name}'.")
        return False
    if not card.mana_cost:
        print(f"✨ Mana Cost missing for '{card.name}'.")
        return False

    if age > timedelta(hours=24):
        print(f"🕒 Cache Stale: '{card.name}' is >24h old.")
        return False

    return True


def add_card_to_container(container, card_name, quantity=1):
    """
    The Bridge Function.
    1. Resolves the card (Local DB or Scryfall)
    2. DIRECTLY updates the container's JSON dictionary (Service Layer logic)
    3. Saves the container
    """
    card_def = get_card_data(card_name)

    if card_def:
        sid = str(card_def.scryfall_id)

        current_count = container.cards.get(sid, 0)
        container.cards[sid] = current_count + quantity

        container.save()

        return card_def

    return None


def remove_card_from_container(container, scryfall_id, quantity=1):
    """
    Removes a specific quantity of a card from the container.
    If count drops to <= 0, the key is removed entirely.
    """
    sid = str(scryfall_id)

    if sid in container.cards:
        container.cards[sid] -= quantity

        if container.cards[sid] <= 0:
            del container.cards[sid]

        container.save()
        return True

    return False