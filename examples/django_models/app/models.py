from __future__ import unicode_literals

from django.utils.encoding import python_2_unicode_compatible
from django.db import models


@python_2_unicode_compatible
class Tag(models.Model):
    word = models.TextField(primary_key=True)

    def __str__(self):
        return self.word


@python_2_unicode_compatible
class Image(models.Model):
    url = models.TextField()

    def __str__(self):
        return self.url


@python_2_unicode_compatible
class Event(models.Model):
    title = models.TextField()
    text = models.TextField()
    runtime = models.IntegerField(null=True)
    is_paid = models.BooleanField()
    min_age = models.IntegerField()

    places = models.ManyToManyField('Place', through='Session')
    tags = models.ManyToManyField('Tag')
    gallery = models.ManyToManyField('Image')

    def __str__(self):
        return self.title


@python_2_unicode_compatible
class Person(models.Model):
    full_name = models.TextField()

    def __str__(self):
        return self.full_name


@python_2_unicode_compatible
class Place(models.Model):
    type = models.TextField()
    title = models.TextField()
    lat = models.FloatField(null=True)
    lon = models.FloatField(null=True)

    events = models.ManyToManyField('Event', through='Session')
    tags = models.ManyToManyField('Tag')
    gallery = models.ManyToManyField('Image')
    persons = models.ManyToManyField('Person', through='Membership')

    def __str__(self):
        return self.title


@python_2_unicode_compatible
class Membership(models.Model):
    place = models.ForeignKey(Place, related_name='members')
    person = models.ForeignKey(Person)
    role = models.TextField()

    def __str__(self):
        return '{}, {} in {}'.format(self.person, self.role, self.place)


@python_2_unicode_compatible
class Session(models.Model):
    time = models.DateTimeField()
    event = models.ForeignKey(Event)
    place = models.ForeignKey(Place)

    def __str__(self):
        return '{}, {}, {}'.format(self.event, self.place, self.time)
