import requests
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone
from django.utils.timezone import is_naive, make_aware, get_current_timezone
from functools import reduce

from .models import CardDefinition

SCRYFALL_API_URL = "https://api.scryfall.com/cards/named"

def get_card_data(card_name):
    """
    Fetches card data.
    Refreshes from Scryfall if:
    1. Data is older than 24 hours
    2. Price is missing
    3. Mana Cost is missing (Self-Healing)
    """

    search_words = card_name.strip().split()
    query_parts = [Q(name__icontains=word) for word in search_words]
    if query_parts:
        query = reduce(lambda q1, q2: q1 & q2, query_parts)
    else:
        return None

    existing_card = CardDefinition.objects.filter(query).first()

    if existing_card:
        last_updated_time = existing_card.last_updated

        if is_naive(last_updated_time):
            last_updated_time = make_aware(last_updated_time, timezone=get_current_timezone())

        age = timezone.now() - last_updated_time

        print(f"DEBUG: Last Updated: {existing_card.last_updated}")
        print(f"DEBUG: Current Time: {timezone.now()}")
        print(f"DEBUG: Age Delta: {age}")

        if existing_card.current_eur is None:
            print(f"💰 Price missing for '{card_name}'. Forcing refresh...")
        elif not existing_card.mana_cost:
            print(f"✨ Mana Cost missing for '{card_name}'. Forcing refresh...")
        elif age < timedelta(hours=24):
            print(f"✅ Cache Hit: Found '{existing_card.name}' (Input: '{card_name}')")
            return existing_card
        else:
            print(f"🔄 Cache Stale: '{card_name}' is old. Refreshing...")


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

        print(f"💾 Saved '{card.name}' [Mana: {mana_cost}]")
        return card

    except requests.RequestException as e:
        print(f"⚠️ Network Error: {e}")
        if existing_card: return existing_card
        return None