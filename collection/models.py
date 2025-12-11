from django.db import models
from account.models import CustomUser as User

class CardDefinition(models.Model):
    """
        The Single Source of Truth.
        Lazy-loaded from Scryfall.
    """
    scryfall_id = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=255, db_index=True)

    image_url = models.URLField(max_length=500, blank=True, null=True)
    image_url_back = models.URLField(max_length=500, blank=True, null=True)

    mana_cost = models.CharField(max_length=50, blank=True, null=True)
    type_line = models.CharField(max_length=255, blank = True, null=True)
    current_eur = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class BaseStorage(models.Model):
    name = models.CharField(max_length=100)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    cards = models.JSONField(default=dict, blank=True)

    class Meta:
        abstract = True

class Collection(BaseStorage):
    description = models.TextField(blank=True, null=True)

class Deck(BaseStorage):
    description = models.TextField(blank=True, null=True)
    format = models.CharField(max_length= 50, blank=True, null=True)