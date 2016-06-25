from unittest import TestCase

from xmlmapper import XMLMapper

# class TestCase:
#     pass

class JsonDumpFactory:
    def create(self, obj_type, fields):
        obj = {'_type': obj_type}
        for k, v in fields:
            if isinstance(v, dict) and hasattr(v, '_type'):
                fields[k] = (v['_type'], v['id'])
            else:
                fields[k] = v
        return obj


class XMLMapperTestCase(TestCase):
    def load(self, mapping, xml):
        mapper = XMLMapper(mapping)
        return mapper.load(xml, JsonDumpFactory())


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
        assert data == [{'_type': 'a', 'id': 10, 'n': 123}]

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
    """

    def test_m2m_nested(self):
        data = self.load(
            [{
                '_type': 'a',
                '_match': 'alist/a',
                '_id': '@id',
                'id': '@id',
            }, {
                '_type': 'b',
                '_match': 'blist/b',
                '_id': '@id',
                'id': '@id',
                '_a': {
                    '_type': 'ab',
                    '_match': 'aref',
                    'a': 'a: @aid',
                    'b': 'b: ../@id',
                }
            }],
            self.XML
        )
        self.assertEqual(
            [
                {'_type': 'a', 'id': 10},
                {'_type': 'a', 'id': 11},
                {'_type': 'b', 'id': 20},
                {'_type': 'b', 'id': 21},
                {'_type': 'b', 'id': 22},
                {'_type': 'ab', 'a': ('a', 21), 'b': ('b', 22)},
                {'_type': 'ab', 'b': ('a', 22), 'b': ('b', 22)},
            ],
            data)

    def test_m2m_separate(self):
        data = self.load(
            [
                {
                    '_type': 'a',
                    '_match': 'alist/a',
                    '_id': '@id',
                    'id': '@id',
                },
                {
                    '_type': 'b',
                    '_match': 'blist/b',
                    '_id': '@id',
                    'id': '@id',
                },
                {
                    '_match': 'b/aref',
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
                {'_type': 'ab', 'a': ('a', 21), 'b': ('b', 22)},
                {'_type': 'ab', 'b': ('a', 22), 'b': ('b', 22)},
            ],
            data)



