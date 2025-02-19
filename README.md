# Optimal Fuel Route Planner

## Overview

This Django-based API calculates an optimal USA road trip route with cost-effective fuel stops based on fuel prices. The system minimizes external API calls by making a single request to fetch the route from a third-party service and processes fuel stops using a pretty simplistic approach.

## How It Works

1. **Route Calculation**: The API fetches a route between the given origin and destination using HERE Maps API.
2. **Fuel Stops Selection**: The system identifies potential fuel stops along the route based on:
   - A predefined vehicle fuel range.
   - A search radius for nearby fuel stations.
   - Prioritization of stations with the lowest fuel price.
3. **Fuel Cost Estimation**: The API calculates the additional fuel cost required for the journey, assuming a full tank at origin.

## Key Features

- **Efficient Routing**: Uses HERE Maps API for routing, making only one third-party API call per request.
- **Optimized Fuel Stops**: Finds the cheapest available fuel stops within a defined radius along the route.
- **GIS Integration**: Uses Django's GIS features to perform geospatial queries and calculations.
- **Caching**: Implements caching to avoid redundant route calculations.

## Data Persistence

Fuel station data is stored in a PostgreSQL/PostGIS database. The dataset, provided as a CSV file, was imported using a Django management command:

```sh
python manage.py import_fuel_stations <path_to_csv>
```

This script, located at `<root>/route_planner/management/commands/import_fuel_stations.py`, reads the CSV file and saves station data into the database.

## API Usage

### Endpoint

```
GET /api/v1/routes/optimal
```

#### Query Parameters:

- `origin_lat`: Latitude of the starting location.
- `origin_lng`: Longitude of the starting location.
- `dest_lat`: Latitude of the destination.
- `dest_lng`: Longitude of the destination.

#### Example Request:

```
GET /api/v1/routes/optimal/?origin_lat=40.7128&origin_lng=-74.0060&dest_lat=41.8781&dest_lng=-87.6298
```

#### Example Response:

```json
{
  "total_distance": 791.3436564057316,
  "total_refill_cost": "89.27978460616290031176422261",
  "fuel_stops": [
    {
      "station": "SHELL/ONE9 #1304 - SRID=4326;POINT (-74.06237 40.60021) - ($2.89233333000000/gal)",
      "distance_from_start": 0.2831570566163623,
      "coordinates": [40.60021, -74.06237],
      "gallons_needed": 0.028315705661633217,
      "cost": "$ 0.08189845924761145576422261000"
    },
    {
      "station": "COLUMBIA TRUCK STOP - SRID=4326;POINT (-75.06372 40.88977) - ($3.07900000000000/gal)",
      "distance_from_start": 81.52285506708482,
      "coordinates": [40.88977, -75.06372],
      "gallons_needed": 8.123969801046847,
      "cost": "$ 25.01370301742324191300000000"
    },
    {
      "station": "SHEETZ #639 - SRID=4326;POINT (-80.7729 41.12367) - ($3.05900000000000/gal)",
      "distance_from_start": 503.1814001578679,
      "coordinates": [41.12367, -80.7729],
      "gallons_needed": 20.982080133864677,
      "cost": "$ 64.18418312949204694300000000"
    }
  ],
  "route_polyline": ["<encoded_polyline_string>"]
}
```

## Test Cases

The following test cases were used to validate the system:

1. **Short Route (City to Nearby City) – Philadelphia to Pittsburgh**

   - Start: (39.9526, -75.1652) (Philadelphia, PA)
   - End: (40.4406, -79.9959) (Pittsburgh, PA)

2. **Long Highway Route – New York to Chicago**

   - Start: (40.7128, -74.0060) (New York, NY)
   - End: (41.8781, -87.6298) (Chicago, IL)

3. **Sparse Fuel Station Route – Rural Midwest**

   - Start: (38.6270, -90.1994) (St. Louis, MO)
   - End: (39.7392, -104.9903) (Denver, CO)

4. **Coast-to-Coast Route – Los Angeles to Miami**

   - Start: (34.0522, -118.2437) (Los Angeles, CA)
   - End: (25.7617, -80.1918) (Miami, FL)

5. **Short Local Route – Within a State**
   - Start: (30.2672, -97.7431) (Austin, TX)
   - End: (29.7604, -95.3698) (Houston, TX)

These test cases ensure the algorithm works across different travel scenarios, from short city trips to long cross-country journeys.

## Installation & Setup

1. Clone the repository:
   ```sh
   git clone <repository_url>
   cd <root>
   ```
2. Python version: 3.12.9
3. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```
4. Set up the database:
   ```sh
   python manage.py migrate
   ```
5. Import fuel station data:
   ```sh
   python manage.py import_fuel_stations <path_to_csv>
   ```
6. Start the Django server:
   ```sh
   python manage.py runserver
   ```
7. Access the API at `http://127.0.0.1:8000/api/v1/routes/optimal`

## Conclusion

This API provides a simplistic cost-effective fuel stop strategy for long-distance travel in the USA. Further enhancements/ optimisations are absolutely necessary to be anywhere near production grade. I don't have the bandwidth for it at the moment.
