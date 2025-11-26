import requests
from datetime import timedelta
from django.utils import timezone
from django.db.models import Q
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

    existing_card = CardDefinition.objects.filter(
        Q(name__iexact=card_name) |
        Q(name__istartswith=f"{card_name} //")
    ).first()

    if existing_card:
        age = timezone.now() - existing_card.last_updated

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
            }
        )

        print(f"💾 Saved '{card.name}' [Mana: {mana_cost}]")
        return card

    except requests.RequestException as e:
        print(f"⚠️ Network Error: {e}")
        if existing_card: return existing_card
        return None