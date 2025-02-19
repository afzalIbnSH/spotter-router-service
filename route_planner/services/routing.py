from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional, Tuple

import flexpolyline
import requests
from django.contrib.gis.db.models import GeometryField
from django.contrib.gis.geos import LineString, Point
from django.contrib.gis.measure import D
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db.models import F, FloatField, Func, Value

from config import settings
from route_planner.models import FuelStation

RANGE_IN_MILES = 500
MILES_PER_GALLON = 10
SEARCH_RADIUS_IN_MILES = 10  # radius to search for stations near route
SAFETY_MARGIN = 0.9  # Don't use more than 90% of the fuel
MAX_TRAVERSIBLE_RANGE = RANGE_IN_MILES * SAFETY_MARGIN
CACHE_TIMEOUT = 3600  # 1 hour cache for routes
HERE_ROUTING_ENDPOINT = "https://router.hereapi.com/v8/routes"
METERS_PER_MILE = 1609.34
MILES_PER_DEGREE = 69.0  # For simplistic rough calculation
DEFAULT_FUEL_COST_IN_USD = Decimal("3.50")


@dataclass
class RouteSegment:
    start_point: Tuple[float, float]
    end_point: Tuple[float, float]
    distance: float
    polyline: str


@dataclass
class Route:
    segments: List[RouteSegment]
    distance: float
    route_line: LineString


@dataclass
class FuelStop:
    station: str
    distance_from_start: float
    coordinates: Tuple[float, float]
    gallons_to_fill: float = None  # to meet max range or reach destination
    cost: Decimal = None  # to fill in the required gallons


class OptimalFuelRouter:
    def __init__(self, origin: Tuple[float, float], destination: Tuple[float, float]):
        self.origin = origin
        self.destination = destination
        self.route_segments: List[RouteSegment] = []
        self.total_distance: float = 0
        self.route_line: LineString = None

    @staticmethod
    def _calculate_fuel_cost(gallons: float, price_per_gallon: Decimal) -> Decimal:
        """Calculate fuel cost for given gallons and price"""
        return Decimal(str(gallons)) * price_per_gallon

    def _calculate_distance_to_point(self, point: Point, distance_covered: float) -> float:
        """Calculate distance to a point considering the distance covered so far in route"""
        # Simplified implementation by transforming the route and location to a projected coordinate system
        # (Web Mercator - meters) and assuming a linear detour
        route_proj: LineString = self.route_line.transform(3857, clone=True)
        point_proj: Point = point.transform(3857, clone=True)
        distance_meters = route_proj.distance(point_proj)
        return distance_covered + (distance_meters / METERS_PER_MILE)

    @staticmethod
    def _decode_polyline(polyline: str) -> List[Tuple[float, float]]:
        """Decode HERE Maps flexible polyline"""
        return flexpolyline.decode(polyline)

    def get_route(self) -> bool:
        """Fetch and process route"""
        cache_key = f"route_{self.origin[0]}_{self.origin[1]}_{self.destination[0]}_{self.destination[1]}"
        cached_route: Route = cache.get(cache_key)

        if cached_route:
            self.route_segments = cached_route.segments
            self.total_distance = cached_route.distance
            self.route_line = cached_route.route_line
            return True

        try:
            response = requests.get(
                HERE_ROUTING_ENDPOINT,
                params={
                    "transportMode": "truck",
                    "origin": f"{self.origin[0]},{self.origin[1]}",
                    "destination": f"{self.destination[0]},{self.destination[1]}",
                    "return": "polyline,summary",
                    "apiKey": settings.HERE_API_KEY,
                },
            )
            response.raise_for_status()
            route_data = response.json()

            coordinates = []
            current_distance = 0

            for section in route_data["routes"][0]["sections"]:
                polyline = section["polyline"]
                section_coords = self._decode_polyline(polyline)
                distance = section["summary"]["length"] / METERS_PER_MILE

                self.route_segments.append(
                    RouteSegment(
                        start_point=section_coords[0],
                        end_point=section_coords[-1],
                        distance=distance,
                        polyline=polyline,
                    )
                )
                coordinates.extend(section_coords)
                current_distance += distance

            self.total_distance = current_distance
            self.route_line = LineString([Point(lng, lat) for lat, lng in coordinates], srid=4326)

            cache.set(
                cache_key,
                Route(segments=self.route_segments, distance=self.total_distance, route_line=self.route_line),
                CACHE_TIMEOUT,
            )

            return True

        except requests.exceptions.RequestException as e:
            print(f"Error fetching route: {str(e)}")
            return False

    def _find_stations_along_route(self) -> List[FuelStation]:
        """Find fuel stations along route"""
        return list(
            FuelStation.objects.annotate(
                station_fraction=Func(
                    Value(self.route_line, output_field=GeometryField()),
                    F("location"),
                    function="ST_LineLocatePoint",
                    output_field=FloatField(),
                )
            )
            .filter(
                location__distance_lte=(self.route_line, D(mi=SEARCH_RADIUS_IN_MILES)),
            )
            .order_by("price_per_gallon_in_usd")
        )

    def _find_next_best_fuel_station(
        self,
        current_point: Point,
        distance_covered: float,
        remaining_distance: float,
        stations_along_route: List[FuelStation],
    ) -> Optional[Tuple[FuelStop, Point]]:
        """Find the next best (cheapest) reachable station

        A simplistic approach that finds all the possible stations within the current and target points
        in the route based on max traversable distance and chooses the cheapest option from it.
        """
        current_fraction: float = self.route_line.project(current_point) / self.route_line.length

        target_distance = distance_covered + MAX_TRAVERSIBLE_RANGE
        target_point: Point = self.route_line.interpolate(target_distance / MILES_PER_DEGREE)
        target_fraction: float = self.route_line.project(target_point) / self.route_line.length

        next_best_station = None
        for station in stations_along_route:
            if current_fraction < station.station_fraction <= target_fraction:
                next_best_station = station
                break
        if not next_best_station:
            return None

        distance_from_start: float = (next_best_station.station_fraction * self.route_line.length) * MILES_PER_DEGREE
        nearby_point_in_route: Point = self.route_line.interpolate(distance_from_start / MILES_PER_DEGREE)

        remaining_distance_from_station = self.total_distance - distance_from_start
        remaining_fuel_at_station = (
            RANGE_IN_MILES - (remaining_distance - remaining_distance_from_station)
        ) / MILES_PER_GALLON

        if remaining_distance_from_station < RANGE_IN_MILES:
            gallons_to_fill = (remaining_distance_from_station / MILES_PER_GALLON) - remaining_fuel_at_station
        else:
            gallons_to_fill = (RANGE_IN_MILES / MILES_PER_GALLON) - remaining_fuel_at_station
        cost = self._calculate_fuel_cost(gallons_to_fill, next_best_station.price_per_gallon_in_usd)

        return (
            FuelStop(
                station=str(next_best_station),
                distance_from_start=distance_from_start,
                coordinates=(next_best_station.location.y, next_best_station.location.x),
                gallons_to_fill=gallons_to_fill,
                cost=cost,
            ),
            nearby_point_in_route,
        )

    def find_optimal_fuel_stops(self) -> Tuple[List[FuelStop], Decimal]:
        """Find optimal fuel stops along route"""
        if not self.route_line:
            raise ValidationError("Route not found")

        stations_along_route = self._find_stations_along_route()

        current_point: Point = self.route_line.interpolate(0)
        distance_covered: float = 0
        optimal_stops: List[FuelStop] = []
        total_refill_cost = Decimal("0")

        while distance_covered < self.total_distance:
            remaining_distance = self.total_distance - distance_covered
            if remaining_distance < MAX_TRAVERSIBLE_RANGE:
                break

            res = self._find_next_best_fuel_station(
                current_point, distance_covered, remaining_distance, stations_along_route
            )
            if not res:
                raise ValidationError("Not enough fuel stations found along the route")

            next_best_fuel_station, nearby_point_in_route = res

            current_point = nearby_point_in_route
            distance_covered = next_best_fuel_station.distance_from_start
            optimal_stops.append(next_best_fuel_station)
            total_refill_cost += next_best_fuel_station.cost

        return optimal_stops, total_refill_cost
