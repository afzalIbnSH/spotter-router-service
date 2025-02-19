from django.core.exceptions import ValidationError
from django.http import JsonResponse

from route_planner.services.routing import OptimalFuelRouter


def get_optimal_route(request):
    """API endpoint for optimal route calculation"""
    try:
        origin = (float(request.GET.get("origin_lat")), float(request.GET.get("origin_lng")))
        destination = (float(request.GET.get("dest_lat")), float(request.GET.get("dest_lng")))
    except (TypeError, ValueError):
        return JsonResponse({"error": "Invalid coordinates provided"}, status=400)

    router = OptimalFuelRouter(origin, destination)
    if not router.get_route():
        return JsonResponse({"error": "Could not calculate route"}, status=400)

    try:
        optimal_stops, total_refill_cost = router.find_optimal_fuel_stops()
    except ValidationError as e:
        return JsonResponse({"error": e.message}, status=400)

    response_data = {
        "total_distance": router.total_distance,
        "total_refill_cost": str(total_refill_cost),
        "fuel_stops": [
            {
                "station": stop.station,
                "distance_from_start": stop.distance_from_start,
                "coordinates": stop.coordinates,
                "gallons_needed": stop.gallons_to_fill,
                "cost": f"$ {str(stop.cost)}",
            }
            for stop in optimal_stops
        ],
        "route_polyline": [segment.polyline for segment in router.route_segments],
    }

    return JsonResponse(response_data)
