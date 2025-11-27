from django.shortcuts import render

from .services import get_card_data

def card_search(request):
    query = request.GET.get('q')
    context = {}

    if query:
        card = get_card_data(query)
        context['card'] = card

    #If HTMX request - return partial HTML
    if request.headers.get('HX-Request'):
        return render(request, 'collection/partials/card_result.html', context)

    #If not HTMX request - render full page
    return render(request, 'collection/search.html', context)