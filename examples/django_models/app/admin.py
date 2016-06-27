from django.contrib import admin

from .models import Event, Tag, Place, Session


class SheduleInline(admin.TabularInline):
    model = Session
    extra = 1


class EventAdmin(admin.ModelAdmin):
    inlines = (SheduleInline,)


class PlaceAdmin(admin.ModelAdmin):
    inlines = (SheduleInline,)


admin.site.register(Event, EventAdmin)
admin.site.register(Tag)
admin.site.register(Place, PlaceAdmin)
admin.site.register(Session)
