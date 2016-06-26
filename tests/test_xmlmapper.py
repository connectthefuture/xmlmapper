import six
from unittest import TestCase

from xmlmapper import MapperObjectFactory, XMLMapper, XMLMappingSyntaxError


class JsonDumpFactory(MapperObjectFactory):
    def create(self, object_type, fields):
        obj = {'_type': object_type}
        for k, v in six.iteritems(fields):
            if isinstance(v, dict) and '_type' in v:
                obj[k] = (v['_type'], v['id'])
            else:
                obj[k] = v
        return obj


class XMLMapperTestCase(TestCase):
    def load(self, mapping, xml):
        mapper = XMLMapper(mapping)
        return mapper.load(xml, JsonDumpFactory())


class TestMappingSyntaxErrors(XMLMapperTestCase):
    def test_mapping_syntax_attribute_errors(self):
        with six.assertRaisesRegex(
                self, XMLMappingSyntaxError, 'required "_type"'):
            XMLMapper([{'_match': '/a'}])
        with six.assertRaisesRegex(
                self, XMLMappingSyntaxError, 'required "_match"'):
            XMLMapper([{'_type': 'a', 'a': 'b'}])
        with six.assertRaisesRegex(
                self, XMLMappingSyntaxError, 'Duplicate mapping type'):
            XMLMapper([
                {'_type': 'a', '_match': 'a'},
                {'_type': 'a', '_match': 'b'},
            ])

    def test_mapping_syntax_value_errors(self):
        with six.assertRaisesRegex(
                self, XMLMappingSyntaxError, '"_type" should be a string'):
            XMLMapper([{'_type': 12, '_match': 'a'}])
        # with six.assertRaisesRegex(
        #         self, MappingSyntaxError, '"Invalid query type"'):
        #     XMLMapper([{'_type': 'a', '_match': 123}])


class TestValueTypes(XMLMapperTestCase):

    def test_value_type_int(self):
        xml = '<a id="10"><n>123</n></a>'
        mapper = XMLMapper([{
            '_type': 'a',
            '_match': '/a',
            'id': 'int: @id',
            'n': 'int: n',
            'no_attr': 'int: @noattr',
            'no_el': 'int: no_el',
        }])
        data = mapper.load(
            xml,
            JsonDumpFactory())
        self.assertEqual(
            [{'_type': 'a', 'id': 10, 'n': 123,
              'no_attr': None, 'no_el': None}],
            data)

    def test_value_type_string(self):
        data = self.load(
            [{
                '_type': 'a',
                '_match': '/a',
                'id': 'string: @id',
                'n': 'string: n',
                'id_def': '@id',
                'n_def': 'n',
            }],
            '<a id="10"><n>123</n></a>'
        )
        self.assertEqual(
            [{'_type': 'a', 'id': '10', 'n': '123',
              'id_def': '10', 'n_def': '123'}],
            data)


class TestManyToManyRelations(XMLMapperTestCase):
    XML = """
        <root>
            <alist>
                <a id="10"></a>
                <a id="11"></a>
            </alist>
            <blist>
                <b id="20">
                    <aref aid="10"></aref>
                    <aref aid="11"></aref>
                </b>
                <b id="21">
                </b>
                <b id="22">
                    <aref aid="11"></aref>
                </b>
            </blist>
        </root>
    """

    def test_m2m_separate(self):
        data = self.load(
            [
                {
                    '_type': 'a',
                    '_match': '/root/alist/a',
                    '_id': '@id',
                    'id': 'int: @id',
                },
                {
                    '_type': 'b',
                    '_match': '/root/blist/b',
                    '_id': '@id',
                    'id': 'int: @id',
                },
                {
                    '_type': 'ab',
                    '_match': '/root/blist/b/aref',
                    'a': 'a: @aid',
                    'b': 'b: ../@id',
                }
            ],
            self.XML
        )
        self.assertEqual(
            [
                {'_type': 'a', 'id': 10},
                {'_type': 'a', 'id': 11},
                {'_type': 'b', 'id': 20},
                {'_type': 'b', 'id': 21},
                {'_type': 'b', 'id': 22},
                {'_type': 'ab', 'a': ('a', 10), 'b': ('b', 20)},
                {'_type': 'ab', 'a': ('a', 11), 'b': ('b', 20)},
                {'_type': 'ab', 'a': ('a', 11), 'b': ('b', 22)},
            ],
            data)



