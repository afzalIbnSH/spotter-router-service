import csv
import os.path
import time
from decimal import Decimal
from typing import Any, Tuple

import requests
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand

from config import settings
from route_planner.models import FuelStation

HERE_GEOCODE_ENDPOINT = "https://geocode.search.hereapi.com/v1/geocode"


class Command(BaseCommand):
    help = "Import fuel stations from CSV and geocode addresses using OpenStreetMap"

    def _geocode_address(self, row: dict[str, Any]) -> None | Tuple[float, float]:
        address = f"{row['Truckstop Name'].strip()}, {row['Address'].strip()}, {row['City'].strip()}, {row['State'].strip()}, USA"  # noqa: E501
        try:
            time.sleep(0.2)

            self.stdout.write(f"Geocoding q: {address}")
            response = requests.get(
                HERE_GEOCODE_ENDPOINT,
                params={
                    "q": address,
                    "apiKey": settings.HERE_API_KEY,
                },
            )
            response.raise_for_status()
            result = response.json()
            if not result["items"]:
                return None
            return (float(result["items"][0]["position"]["lat"]), float(result["items"][0]["position"]["lng"]))

        except requests.exceptions.RequestException as e:
            if e.response.status_code == 429:
                raise e
            self.stdout.write(self.style.ERROR(f"Error geocoding {row['Truckstop Name']}: {str(e)}"))

    def handle(self, *args, **kwargs):
        row_count = 0
        with open(os.path.join(settings.BASE_DIR, "fuel-prices-for-be-assessment.csv"), "r") as file:
            row_count = len(file.readlines())

        with open(os.path.join(settings.BASE_DIR, "fuel-prices-for-be-assessment.csv"), "r") as file:
            for index, row in enumerate(csv.DictReader(file)):
                self.stdout.write(f"Processing row number {index}. Rows left: {row_count - index - 1}.")

                if FuelStation.objects.filter(
                    name=row["Truckstop Name"], address=row["Address"], city=row["City"], state=row["State"]
                ).exists():
                    self.stdout.write(self.style.SUCCESS(f"Skipping duplicate station: {row['Truckstop Name']}"))
                    continue

                geocode = self._geocode_address(row)
                if not geocode:
                    self.stdout.write(self.style.WARNING(f"Could not geocode address for: {row['Truckstop Name']}"))
                    continue
                (latitude, longitude) = geocode

                x = longitude
                y = latitude
                station = FuelStation(
                    name=row["Truckstop Name"].strip(),
                    address=row["Address"].strip(),
                    city=row["City"].strip(),
                    state=row["State"].strip(),
                    price_per_gallon_in_usd=Decimal(str(row["Retail Price"]).strip()),
                    location=Point(x, y, srid=4326),
                )
                station.save()
                self.stdout.write(self.style.SUCCESS(f"Successfully imported: {station}"))
