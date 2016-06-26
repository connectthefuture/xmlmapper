import six
from unittest import TestCase

from xmlmapper import MapperObjectFactory, XMLMapper, XMLMapperSyntaxError, \
    XMLMapperLoadingError


class JsonDumpFactory(MapperObjectFactory):

    def _convert(self, value):
        if isinstance(value, dict) and '_type' in value:
            return (value['_type'], value['id'])
        elif isinstance(value, list):
            return [self._convert(x) for x in value]
        return value

    def create(self, object_type, fields):
        obj = {'_type': object_type}
        for k, v in six.iteritems(fields):
            obj[k] = self._convert(v)
        return obj


class XMLMapperTestCase(TestCase):
    def load(self, mapping, xml):
        mapper = XMLMapper(mapping)
        return mapper.load(xml, JsonDumpFactory())


class TestMapperSyntaxErrors(XMLMapperTestCase):
    def test_mapper_syntax_attribute_errors(self):
        with six.assertRaisesRegex(
                self, XMLMapperSyntaxError, 'required "_type"'):
            XMLMapper([{'_match': '/a'}])
        with six.assertRaisesRegex(
                self, XMLMapperSyntaxError, 'required "_match"'):
            XMLMapper([{'_type': 'a', 'a': 'b'}])
        with six.assertRaisesRegex(
                self, XMLMapperSyntaxError, 'Duplicate mapping type'):
            XMLMapper([
                {'_type': 'a', '_match': 'a'},
                {'_type': 'a', '_match': 'b'},
            ])

    def test_mapper_syntax_value_errors(self):
        with six.assertRaisesRegex(
                self, XMLMapperSyntaxError, '"_type" should be a string'):
            XMLMapper([{'_type': 12, '_match': 'a'}])
        with six.assertRaisesRegex(
                self, XMLMapperSyntaxError, '"_match" should be a string'):
            XMLMapper([{'_type': 'a', '_match': 123}])


class TestMapperLoadingErrors(XMLMapperTestCase):

    def assert_loading_error(self, mapper, xml, message, tag, line):
        try:
            mapper.load(xml, JsonDumpFactory())
            self.fail('XMLMapperLoadingError not raised')
        except XMLMapperLoadingError as e:
            self.assertEqual(e.element_tag, tag)
            self.assertEqual(e.source_line, line)
        # except Exception, e:
        #     raise

    def test_mapper_loading_id_errors(self):
        mapper = XMLMapper([{
            '_type': 'a',
            '_match': '/r/a',
            '_id': '@id',
        }])

        self.assert_loading_error(
            mapper,
            b'<r>\n<a></a></r>',
            '"_id" is None',
            'a', 2)

        self.assert_loading_error(
            mapper,
            b'<r><a id="1"></a><a id="1"></a></r>',
            'Duplicate object',
            'a', 1)

    def test_mapper_loading_ref_errors(self):
        mapper = XMLMapper([
            {
                '_type': 'a',
                '_match': '/r/a',
                '_id': '@id',
            }, {
                '_type': 'b',
                '_match': '/r/b',
                'a': 'a: @aid',
            }
        ])

        self.assert_loading_error(
            mapper,
            b'<r>\n<a id="1">\n</a>\n<b aid="2"></b></r>',
            'Referenced undefined',
            'b', 4)

    def test_mapper_loading_string_errors(self):
        mapper = XMLMapper([{
            '_type': 'a',
            '_match': '/r/a',
            '_id': '@id',
            'b': 'b'
        }])

        self.assert_loading_error(
            mapper,
            b'<r><a><b></b><b></b></a></r>',
            'multiple elements',
            'a', 1)

    def test_mapper_loading_int_errors(self):
        mapper = XMLMapper([{
            '_type': 'a',
            '_match': '/r/a',
            '_id': '@id',
            'b': 'int: b'
        }])

        self.assert_loading_error(
            mapper,
            b'<r><a><b></b><b></b></a></r>',
            'multiple elements',
            'a', 1)

        self.assert_loading_error(
            mapper,
            b'<r><a><b>aoeu</b></a></r>',
            'Invalid literal for int: "aoeu"',
            'a', 1)


class TestValueTypes(XMLMapperTestCase):

    def test_value_type_int(self):
        xml = b'<a id="10"><n>123</n></a>'
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
            b'<a id="10"><n>123</n></a>'
        )
        self.assertEqual(
            [{'_type': 'a', 'id': '10', 'n': '123',
              'id_def': '10', 'n_def': '123'}],
            data)


class TestNestedMappings(XMLMapperTestCase):
    def test_nested_mappings(self):
        data = self.load(
            [{
                '_type': 'a',
                '_match': '/r/a',
                'id': '@id',
                'b': {
                    '_type': 'b',
                    '_match': './b',
                    'id': '@id'
                }
            }],
            b'<r><a id="10"><b id="20"></b></a>'
            b'<a id="11"><b id="21"></b><b id="22"></b></a>'
            b'<a id="12"></a></r>'
        )
        print(data)
        self.assertEqual(
            [
                {'_type': 'b', 'id': '20'},
                {'_type': 'a', 'id': '10', 'b': [('b', '20')]},
                {'_type': 'b', 'id': '21'},
                {'_type': 'b', 'id': '22'},
                {'_type': 'a', 'id': '11', 'b': [('b', '21'), ('b', '22')]},
                {'_type': 'a', 'id': '12', 'b': []},
            ],
            data)


class TestManyToManyRelations(XMLMapperTestCase):
    XML = b"""
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


class TestMapperReuse(XMLMapperTestCase):

    def test_mapper_reuse(self):
        mapper = XMLMapper([{
            '_type': 'a',
            '_match': '/a',
            'id': '@id',
        }])

        data = mapper.load(
            b'<a id="10"></a>',
            JsonDumpFactory())
        self.assertEqual(
            [{'_type': 'a', 'id': '10'}],
            data)

        data2 = mapper.load(
            b'<a id="11"></a>',
            JsonDumpFactory())
        self.assertEqual(
            [{'_type': 'a', 'id': '11'}],
            data2)

    def test_mapper_state_reset(self):
        mapper = XMLMapper([
            {
                '_type': 'a',
                '_match': '/r/a',
                '_id': '@id',
                'id': 'string: @id',
            }, {
                '_type': 'b',
                '_match': '/r/b',
                'a': 'a: @aid',
            }
        ])

        data = mapper.load(
            b'<r><a id="10"></a><b aid="10"></b></r>',
            JsonDumpFactory())
        self.assertEqual(
            [
                {'_type': 'a', 'id': '10'},
                {'_type': 'b', 'a': ('a', '10')}],
            data)

        with self.assertRaises(XMLMapperLoadingError):
            mapper.load(
                b'<r><a id="11"></a><b aid="10"></b></r>',
                JsonDumpFactory())
