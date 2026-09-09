from django.shortcuts import render


def map_view(request):
    ### Render the main earthquake map page.
    ### Earthquake data will be loaded asynchronously from the API
    ### by the frontend once the map interface is implemented.
    return render(request, "map/map.html")