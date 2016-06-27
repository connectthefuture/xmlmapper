from tempfile import NamedTemporaryFile
import os
import pytz
from datetime import datetime

from django.test import TestCase
from django.core import management

from app.models import Event, Place, Tag, Image, Person, Membership, Session


class CommandTestCase(TestCase):
    def setUp(self):
        self.file = NamedTemporaryFile(delete=False)
        self.file.write(self.XML)
        self.file.close()

    def tearDown(self):
        os.unlink(self.file.name)


class TestLoadXMLCommandEvents(CommandTestCase):
    XML = b'''
        <feed>
            <events>
                <event id="10" price="True">
                    <title>event1</title>
                    <text>text1</text>
                </event>
                <event id="11">
                    <title>event2</title>
                    <text>text2</text>
                    <runtime>123</runtime>
                    <age_restricted>18+</age_restricted>
                </event>
            </events>
        </feed>
    '''

    def test_loadxml_command_events(self):
        self.assertEqual(Event.objects.count(), 0)

        management.call_command('loadxml', self.file.name, verbosity=0)

        events = Event.objects.all().order_by('id')
        self.assertEqual(len(events), 2)
        e1, e2 = events
        self.assertEqual(e1.title, 'event1')
        self.assertEqual(e1.text, 'text1')
        self.assertEqual(e1.is_paid, True)
        self.assertEqual(e1.runtime, None)
        self.assertEqual(e1.min_age, 0)

        self.assertEqual(e2.title, 'event2')
        self.assertEqual(e2.text, 'text2')
        self.assertEqual(e2.is_paid, False)
        self.assertEqual(e2.runtime, 123)
        self.assertEqual(e2.min_age, 18)


class TestLoadXMLCommandPlaces(CommandTestCase):
    XML = b'''
        <feed>
            <places>
                <place id="20" type="type1">
                    <title>place1</title>
                </place>
                <place id="21" type="type2">
                    <title>place2</title>
                    <coordinates latitude="12.3" longitude="34.5"/>
                </place>
            </places>
        </feed>
    '''

    def test_loadxml_command_places(self):
        self.assertEqual(Place.objects.count(), 0)

        management.call_command('loadxml', self.file.name, verbosity=0)

        places = Place.objects.all().order_by('id')
        self.assertEqual(len(places), 2)
        p1, p2 = places
        self.assertEqual(p1.title, 'place1')
        self.assertEqual(p1.type, 'type1')
        self.assertEqual(p1.lat, None)
        self.assertEqual(p1.lon, None)

        self.assertEqual(p2.title, 'place2')
        self.assertEqual(p2.type, 'type2')
        self.assertAlmostEqual(p2.lat, 12.3)
        self.assertAlmostEqual(p2.lon, 34.5)


class TestLoadXMLCommandTags(CommandTestCase):
    XML = b'''
        <feed>
            <events>
                <event id="10" price="True">
                    <title>event1</title>
                    <text>text1</text>
                    <tags>
                        <tag>tag1</tag>
                    </tags>
                </event>
            </events>
            <places>
                <place id="20" type="type1">
                    <title>place1</title>
                    <tags>
                        <tag>tag1</tag>
                        <tag>tag2</tag>
                    </tags>
                </place>
            </places>
        </feed>
    '''

    def test_loadxml_command_tags(self):
        self.assertEqual(Tag.objects.count(), 0)

        management.call_command('loadxml', self.file.name, verbosity=0)
        self.assertEqual(Tag.objects.count(), 2)
        e = Event.objects.get(title='event1')
        self.assertEqual([t.word for t in e.tags.all()], ['tag1'])
        p = Place.objects.get(title='place1')
        self.assertEqual([t.word for t in p.tags.all()], ['tag1', 'tag2'])


class TestLoadXMLCommandImages(CommandTestCase):
    XML = b'''
        <feed>
            <events>
                <event id="10" price="True">
                    <title>event1</title>
                    <text>text1</text>
                    <gallery>
                        <image href="url1"/>
                    </gallery>
                </event>
            </events>
            <places>
                <place id="20" type="type1">
                    <title>place1</title>
                    <gallery>
                        <image href="url1"/>
                        <image href="url2"/>
                    </gallery>
                </place>
            </places>
        </feed>
    '''

    def test_loadxml_command_images(self):
        self.assertEqual(Image.objects.count(), 0)

        management.call_command('loadxml', self.file.name, verbosity=0)
        self.assertEqual(Image.objects.count(), 2)
        e = Event.objects.get(title='event1')
        self.assertEqual([i.url for i in e.gallery.all()], ['url1'])
        p = Place.objects.get(title='place1')
        self.assertEqual([i.url for i in p.gallery.all()], ['url1', 'url2'])


class TestLoadXMLCommandPersons(CommandTestCase):
    XML = b'''
        <feed>
            <places>
                <place id="20" type="type1">
                    <title>place1</title>
                    <persons>
                        <person>
                            <name>person1</name>
                            <role>author</role>
                        </person>
                        <person>
                            <name>person2</name>
                            <role>actor</role>
                        </person>
                    </persons>
                </place>
                <place id="21" type="type2">
                    <title>place2</title>
                    <persons>
                        <person>
                            <name>person1</name>
                            <role>actor</role>
                        </person>
                    </persons>
                </place>
            </places>
        </feed>
    '''

    def test_loadxml_command_persons(self):
        self.assertEqual(Person.objects.count(), 0)
        self.assertEqual(Membership.objects.count(), 0)

        management.call_command('loadxml', self.file.name, verbosity=0)
        self.assertEqual(Person.objects.count(), 2)
        self.assertEqual(Membership.objects.count(), 3)
        p1 = Place.objects.get(title='place1')
        p2 = Place.objects.get(title='place2')
        self.assertEqual(
            [(m.person.full_name, m.role) for m in p1.members.all()],
            [('person1', 'author'), ('person2', 'actor')])

        self.assertEqual(
            [(m.person.full_name, m.role) for m in p2.members.all()],
            [('person1', 'actor')])


class TestLoadXMLCommandSessions(CommandTestCase):
    XML = b'''
        <feed>
            <events>
                <event id="10" type="type1">
                    <title>event1</title>
                    <text>text1</text>
                </event>
                <event id="11" type="type1">
                    <title>event2</title>
                    <text>text2</text>
                </event>
            </events>
            <places>
                <place id="10" type="type1">
                    <title>place1</title>
                </place>
                <place id="11" type="type2">
                    <title>place2</title>
                </place>
            </places>
            <schedule>
                <session event="10" place="10" date="2000-01-22" time="10:30"/>
                <session event="10" place="11" date="2001-12-23" time="12:30"/>
                <session event="11" place="10" date="2001-11-25" time="01:30"/>
            </schedule>
        </feed>
    '''

    def test_loadxml_command_persons(self):
        self.assertEqual(Session.objects.count(), 0)

        management.call_command('loadxml', self.file.name, verbosity=0)
        self.assertEqual(Session.objects.count(), 3)
        s1, s2, s3 = Session.objects.all()
        e1 = Event.objects.get(title='event1')
        e2 = Event.objects.get(title='event2')

        self.assertEqual([p.title for p in e1.places.all()],
                         ['place1', 'place2'])
        self.assertEqual([p.title for p in e2.places.all()],
                         ['place1'])

        self.assertEqual(s1.time,
                         datetime(2000, 1, 22, 10, 30, tzinfo=pytz.utc))
        self.assertEqual(s2.time,
                         datetime(2001, 12, 23, 12, 30, tzinfo=pytz.utc))
        self.assertEqual(s3.time,
                         datetime(2001, 11, 25, 1, 30, tzinfo=pytz.utc))
