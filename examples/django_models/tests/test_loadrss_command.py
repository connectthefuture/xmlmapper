from tempfile import NamedTemporaryFile
import os

from django.test import TestCase
from django.core import management

from app.models import Event, Tag, Image


class CommandTestCase(TestCase):
    def setUp(self):
        self.file = NamedTemporaryFile(delete=False)
        self.file.write(self.RSS)
        self.file.close()

    def tearDown(self):
        os.unlink(self.file.name)


class TestLoadRSSCommand(CommandTestCase):
    RSS = b'''<?xml version="1.0" encoding="utf-8"?>
    <rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
        <channel>
            <title>channel</title>
            <link>channel_url</link>
            <description>channel_descr</description>
            <item>
                <title>item1</title>
                <link>link1</link>
                <description>descr1</description>
                <category>cat1</category>
                <category>cat2</category>
                <enclosure type="image/jpeg" url="img1url"/>
                <enclosure type="audio/mpeg" url="audio1url"/>
            </item>
            <item>
                <title>item2</title>
                <link>link2</link>
                <description>descr2</description>
                <category>cat2</category>
            </item>
        </channel>
    </rss>
    '''

    def test_loadrss_command(self):
        self.assertEqual(Event.objects.count(), 0)
        self.assertEqual(Tag.objects.count(), 0)
        self.assertEqual(Image.objects.count(), 0)

        management.call_command('loadrss', self.file.name, verbosity=0)

        self.assertEqual(Event.objects.count(), 2)
        self.assertEqual(Tag.objects.count(), 2)
        self.assertEqual(Image.objects.count(), 1)

        e1, e2 = Event.objects.all().order_by('id')

        self.assertEqual(e1.title, 'item1')
        self.assertEqual(e1.text, 'descr1')
        self.assertEqual(e2.title, 'item2')
        self.assertEqual(e2.text, 'descr2')

        self.assertEqual([t.word for t in e1.tags.all()], ['cat1', 'cat2'])
        self.assertEqual([t.word for t in e2.tags.all()], ['cat2'])

        self.assertEqual([i.url for i in e1.gallery.all()], ['img1url'])
        self.assertEqual(e2.gallery.count(), 0)
