from django.db import models


class Area(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Turf(models.Model):
    name = models.CharField(max_length=100)
    area = models.ForeignKey(Area, on_delete=models.CASCADE)
    location = models.CharField(max_length=200, blank=True, null=True)
    price = models.IntegerField(default=500)
    description = models.TextField(blank=True, null=True)

    # NEW FIELD
    owner_phone = models.CharField(max_length=15, blank=True, null=True)

    def __str__(self):
        return self.name


class UserSession(models.Model):
    phone_number = models.CharField(max_length=20, unique=True)
    step = models.CharField(max_length=50, default="start")

    selected_area = models.CharField(max_length=100, blank=True, null=True)
    selected_turf = models.CharField(max_length=100, blank=True, null=True)
    selected_date = models.DateField(blank=True, null=True)
    selected_slot = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.phone_number


class Booking(models.Model):
    area = models.CharField(max_length=100)
    turf = models.CharField(max_length=100)
    date = models.DateField(blank=True, null=True)
    slot = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20)

    def __str__(self):
        return f"{self.turf} - {self.date} - {self.slot}"