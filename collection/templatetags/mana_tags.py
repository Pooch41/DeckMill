import re
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name='mana_icons')
def mana_icons(value):
    """
    Converts Scryfall mana strings like {3}{G}{G} into HTML image tags.
    """
    if not value:
        return ""

    def replace_symbol(match):
        symbol = match.group(1)

        normalized_symbol = symbol.replace("/", "")

        return f'<img src="https://svgs.scryfall.io/card-symbols/{normalized_symbol}.svg" class="mana-pip" alt="{symbol}">'

    html = re.sub(r'\{([A-Z0-9/]+)\}', replace_symbol, value)

    return mark_safe(html)