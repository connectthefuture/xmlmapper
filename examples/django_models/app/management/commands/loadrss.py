from django.core.management.base import BaseCommand

from xmlmapper import XMLMapper

from ._factory import ModelsFactory

# simple rss 2.0 parser, not much data to extract here

_RSS_MAPPINGS = [
    {
        '_type': 'event',
        '_match': '/rss/channel/item',
        'title': 'title',
        'text': 'description',
        'is_paid': 'bool: boolean("true")',
        'runtime': 'int: "0"',
        'min_age': 'int: "0"',
        '#tags': [{
            '_type': 'event_tag',
            '_match': 'category',
            'word': 'text()',
        }],
        '#gallery': [{
            '_type': 'event_image',
            '_match': 'enclosure[@type="image/jpeg"]',
            'url': '@url',
        }],
    }
]


class Command(BaseCommand):
    help = 'Imports RSS 2.0 feed as list of events'

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)

        self.mapper = XMLMapper(_RSS_MAPPINGS)

    def add_arguments(self, parser):
        parser.add_argument('filename', nargs='+')

    def handle(self, *args, **options):
        factory = ModelsFactory()
        for filename in options['filename']:
            if options['verbosity'] > 0:
                self.stdout.write(
                    'Importing {} ... '.format(filename), ending="")
            res = self.mapper.load_file(filename, factory)
            if options['verbosity'] > 0:
                self.stdout.write(self.style.SUCCESS('OK'), ending="")
                self.stdout.write(" ({} objects)".format(len(res)))
