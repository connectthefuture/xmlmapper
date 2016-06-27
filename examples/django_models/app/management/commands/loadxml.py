import pytz
from datetime import datetime

from django.core.management.base import BaseCommand

from xmlmapper import XMLMapper

from ._factory import ModelsFactory


_XML_MAPPINGS = [
    {
        '_type': 'event',
        '_match': '/feed/events/event',
        '_id': '@id',
        'title': 'title',
        'text': 'text',
        'is_paid': 'bool: boolean(@price)',
        'runtime': 'int: runtime',
        'min_age': 'min_age: age_restricted',
        '#tags': [{
            '_type': 'event_tag',
            '_match': 'tags/tag',
            'word': 'text()',
        }],
        '#gallery': [{
            '_type': 'event_image',
            '_match': 'gallery/image',
            'url': '@href',
        }]
    }, {
        '_type': 'place',
        '_match': '/feed/places/place',
        '_id': '@id',
        'type': '@type',
        'title': 'title',
        'lat': 'float: coordinates/@latitude',
        'lon': 'float: coordinates/@longitude',
        '#tags': [{
            '_type': 'place_tag',
            '_match': 'tags/tag',
            'word': 'text()',
        }],
        '#gallery': [{
            '_type': 'place_image',
            '_match': 'gallery/image',
            'url': '@href',
        }],
    }, {
        '_type': 'place_person',
        '_match': '/feed/places/place/persons/person',
        'place': 'place: ../../@id',
        'person': {
            '_type': 'person',
            '_match': 'name',
            'full_name': 'text()',
        },
        'role': 'role',
    }, {
        '_type': 'session',
        '_match': '/feed/schedule/session',
        'event': 'event: @event',
        'place': 'place: @place',
        'time': 'datetime: concat(@date, " ", @time)',
    }
]


class Command(BaseCommand):
    help = 'Imports XML in kudago test format'

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)

        def datetime_filter(value):
            return pytz.utc.localize(
                datetime.strptime(value, '%Y-%m-%d %H:%M'))

        def min_age_filter(value):
            if value is None:
                return 0
            return int(value[:-1])

        self.mapper = XMLMapper(
            _XML_MAPPINGS,
            filters={
                'datetime': datetime_filter,
                'min_age': min_age_filter,
            }
        )

    def add_arguments(self, parser):
        parser.add_argument('filename', nargs='+')

    def handle(self, *args, **options):
        factory = ModelsFactory()
        for filename in options['filename']:
            if options['verbosity'] > 0:
                self.stdout.write(
                    'Importing {} ... '.format(filename), ending="")
            self.mapper.load_file(filename, factory)
            if options['verbosity'] > 0:
                self.stdout.write(self.style.SUCCESS('OK'))
