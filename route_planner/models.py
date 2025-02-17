from django.contrib.gis.db import models
from django.contrib.postgres.indexes import GistIndex


class FuelStation(models.Model):
    name = models.CharField(max_length=255)
    address = models.TextField()
    city = models.CharField(max_length=255)
    state = models.CharField(max_length=255)
    price_per_gallon_in_usd = models.DecimalField(max_digits=16, decimal_places=14)
    location = models.PointField(srid=4326)

    def __str__(self):
        return f"{self.name} - {self.location} - (${self.price_per_gallon_in_usd}/gal)"

    class Meta:
        indexes = [GistIndex(fields=["location"])]
