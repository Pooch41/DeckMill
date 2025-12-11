from django.test import TestCase
from unittest.mock import patch, MagicMock
from django.utils import timezone
from datetime import timedelta
from collection.models import CardDefinition, Deck
from collection.services import get_card_data, add_card_to_container
from account.models import CustomUser


class CardServiceTests(TestCase):
    def setUp(self):
        # Create a dummy user for the deck owner
        self.user = CustomUser.objects.create_user(email="test@example.com", password="password")
        self.deck = Deck.objects.create(name="Test Deck", owner=self.user, format="Standard")

        # Create a "fresh" card in the DB
        self.fresh_card = CardDefinition.objects.create(
            scryfall_id="uuid-123",
            name="Sol Ring",
            mana_cost="{1}",
            current_eur=1.50,
            last_updated=timezone.now()
        )

        # Create a "stale" card (older than 24h)
        self.stale_card = CardDefinition.objects.create(
            scryfall_id="uuid-456",
            name="Black Lotus",
            mana_cost="{0}",
            current_eur=None,  # Missing price forces refresh
            last_updated=timezone.now() - timedelta(hours=25)
        )

    def test_exact_match_hits_local_db(self):
        """Should return the local card immediately if names match exactly."""
        with patch('collection.services.requests.get') as mock_get:
            result = get_card_data("Sol Ring")

            self.assertEqual(result.scryfall_id, "uuid-123")
            self.assertEqual(result.name, "Sol Ring")
            mock_get.assert_not_called()


    def test_single_word_fuzzy_skips_local(self):
        """Searching 'Sol' should SKIP the local 'Sol Ring' and hit API."""
        # Create a mock response for Scryfall
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "uuid-789",
            "name": "Sol Talisman",
            "mana_cost": "{2}",
            "prices": {"eur": "0.50"}
        }

        with patch('collection.services.requests.get', return_value=mock_response) as mock_get:
            result = get_card_data("Sol")

            # Should have called API because "Sol" is 1 word (dangerous)
            mock_get.assert_called_once()
            self.assertEqual(result.name, "Sol Talisman")

    def test_multi_word_fuzzy_hits_local(self):
        """Searching 'Sol Rin' (2 words) should trust local 'Sol Ring'."""
        with patch('collection.services.requests.get') as mock_get:
            result = get_card_data("Sol Rin")

            # Should match 'Sol Ring' locally because len("Sol Rin".split()) > 1
            self.assertEqual(result.name, "Sol Ring")
            mock_get.assert_not_called()


    def test_api_fetch_creates_card(self):
        """If card is missing locally, fetch from API and save to DB."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "uuid-new",
            "name": "New Card",
            "mana_cost": "{R}",
            "prices": {"eur": "5.00"},
            "image_uris": {"normal": "http://img.com"}
        }

        with patch('collection.services.requests.get', return_value=mock_response) as mock_get:
            # Search for a card that doesn't exist in setUp
            result = get_card_data("New Card")

            self.assertEqual(result.scryfall_id, "uuid-new")
            # Verify it was actually saved to DB
            self.assertTrue(CardDefinition.objects.filter(name="New Card").exists())

    def test_api_404_returns_none(self):
        """If Scryfall 404s, return None (don't crash)."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch('collection.services.requests.get', return_value=mock_response):
            result = get_card_data("Nonexistent Card")
            self.assertIsNone(result)


    def test_add_card_to_container(self):
        """Ensure the bridge function updates the deck's JSON dictionary."""
        # Use exact name to hit local cache
        card = add_card_to_container(self.deck, "Sol Ring", quantity=4)

        self.assertIsNotNone(card)

        # Refresh deck from DB to see changes
        self.deck.refresh_from_db()

        # Check the JSON field
        self.assertEqual(self.deck.cards.get("uuid-123"), 4)