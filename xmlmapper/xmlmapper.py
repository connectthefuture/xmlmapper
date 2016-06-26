import re
from io import BytesIO

import six
from lxml import etree

class XMLMapperError(Exception):
    u"""Main exception base class for xmlmapper.  All other exceptions inherit
    from this one."""
    pass


class XMLMappingSyntaxError(XMLMapperError, SyntaxError):
    u"""Error compiling mapping spec."""
    pass


class MapperObjectFactory:
    """Interface for object factory used by `XMLMapper`"""

    def create(self, object_type, fields):
        """Creates object with specified type and attributes

        Args:
            object_type (str): Type of object to create
                as in  "_type" attribute of mapping.
            fields: Dictionary of attributes with values.

        Returns:
            The constructed object.
        """
        raise NotImplementedError


class XMLMapper:
    """Loads data from XML into objects according to provided mappings.
    """

    _RX_QUERY = re.compile(r'(?:(?P<type>\w+)\s*:\s*)?(?P<xpath>.*)')
    _VALUE_TYPES = ('string', 'int')

    class _Query:
        def __init__(self, mapping_type, attr):
            self.mapping_type, self.attr = mapping_type, attr

    class _XPathQuery(_Query):
        """Attribute query ([type:] xpath)."""
        def __init__(self, mapping_type, attr, value_type, xpath):
            XMLMapper._Query.__init__(self, mapping_type, attr)
            self.value_type, self.xpath = value_type, xpath

        def _get_string(self, xpath_query, value):
            if isinstance(value, list):
                if len(value) == 0:
                    return None
                if len(value) > 1:
                    raise ValueError(
                        'XPath "{}" returned multiple elements while single '
                        'value was expected.'.format(xpath_query.xpath))
                value = value[0]
                if hasattr(value, 'text'):
                    value = value.text
            return six.text_type(value).strip()

        def run(self, mapper, element, object_factory, result):
            value = self.xpath(element)
            if self.value_type == 'string':
                return self._get_string(self.xpath, value)
            elif self.value_type == 'int':
                str_value = self._get_string(self.xpath, value)
                if str_value is None:
                    return None
                return int(str_value)
            else:
                obj_id = self._get_string(self.xpath, value)
                obj_key = (self.value_type, obj_id)
                if obj_key not in mapper.objects:
                    raise KeyError('Referenced undefined "{}" object with '
                                   'id "{}"'.format(self.value_type, obj_id))
                return mapper.objects[obj_key]

    class _MappingQuery(_Query):
        """Mapping query, either primary or nested."""
        def __init__(self, mapping_type, attr, match, has_id, compiled):
            XMLMapper._Query.__init__(self, mapping_type, attr)
            self.match, self.has_id, self.compiled = match, has_id, compiled

        def run(self, mapper, element, object_factory, result):
            return mapper._load_mapping(element, self, object_factory, result)

    def __init__(self, mappings):
        """Creates new mapper for provided spec.

        Args:
            mappings: List of mapping specs.
        """
        self._types = {}
        self.objects = {}  # TODO move into separate parsing state
        self._mappings = [self._compile_mapping(None, m) for m in mappings]

    def _compile_mapping(self, attr, mapping, parent=None):
        # Parses and compiles mapping spec (dict)
        # Required attributes: _type, _match
        if '_type' not in mapping:
            raise XMLMappingSyntaxError('Missing required "_type" attribute')
        mtype = mapping['_type']
        if not isinstance(mtype, six.string_types):
            raise XMLMappingSyntaxError('"_type" should be a string')
        if '_match' not in mapping:
            raise XMLMappingSyntaxError(
                'Missing required "_match" attribute '
                'for type {}'.format(mtype))
        if mtype in self._types:
            raise XMLMappingSyntaxError(
                'Duplicate mapping type "{}"'.format(mtype))

        match = self._compile_xpath(mapping['_match'])

        # Iterate and compile mapping attributes (ordered by name)
        compiled = []
        for k in sorted(mapping.keys()):
            v = mapping[k]

            if k == '_type' or k == '_match':
                continue

            if isinstance(v, dict):
                query = self._compile_mapping(k, v, mtype)
            elif isinstance(v, six.string_types):
                query = self._compile_query(mtype, k, v)
            else:
                raise XMLMappingSyntaxError(
                    'Invalid query type {} for "{}" attribute '
                    'in type "{}"'.format(type(v), k, mtype))
            compiled.append(query)

        # Create mapping object and add it to types index
        query_obj = self._MappingQuery(mtype, attr, match,
                                       '_id' in mapping, compiled)
        self._types[mtype] = query_obj
        return query_obj

    def _compile_xpath(self, xpath):
        return etree.XPath(xpath, smart_strings=False)

    def _compile_query(self, mapping_type, attr, query):
        # Parses and compiles attribute query spec:
        # [type:] xpath
        q_match = self._RX_QUERY.match(query)

        if not q_match:
            raise XMLMappingSyntaxError(
                'Invalid query format: {}'.format(query))

        q_type = q_match.group('type')
        if q_type is None:
            q_type = 'string'

        if q_type not in self._VALUE_TYPES:
            if q_type not in self._types:
                raise XMLMappingSyntaxError(
                    'Unknown value type "{}" for "{}" attribute '
                    'in type "{}"'.format(q_type, attr, mapping_type))
            elif not self._types[q_type].has_id:
                raise XMLMappingSyntaxError(
                    'Invalid value type "{}" for "{}" attribute '
                    'in type "{}" (only types with "_id" can be '
                    'referenced)'.format(q_type, attr, mapping_type))

        if attr == '_id' and q_type != 'string':
            raise XMLMappingSyntaxError(
                'In type "{}" attribute "_id" is required '
                'to be a string.'.format(mapping_type))

        q_xpath = self._compile_xpath(q_match.group('xpath'))
        return self._XPathQuery(mapping_type, attr, q_type, q_xpath)

    def load(self, xml, object_factory):
        """Parse XML and load objects according to spec.

        Args:
            xml: String or file-like object to get XML from.
            object_factory: `MapperObjectFactory` for creating objects.

        Returns:
            List of loaded objects as returned by `object_factory`.
        """
        parser = etree.XMLParser(remove_blank_text=True)
        if isinstance(xml, six.string_types):
            xml = BytesIO(xml)
        root = etree.parse(xml, parser)
        result = []
        for mapping in self._mappings:
            self._load_mapping(root, mapping, object_factory, result)
        return result

    def _load_mapping(self, element, mapping, object_factory, result):
        for element in mapping.match(element):

            # load attributes
            internal_data = {}
            data = {}
            for query in mapping.compiled:
                value = query.run(self, element, object_factory, result)
                if query.attr.startswith('_'):
                    internal_data[query.attr] = value
                else:
                    data[query.attr] = value

            obj = object_factory.create(mapping.mapping_type, data)

            if mapping.has_id:
                # add object to index
                assert '_id' in internal_data
                obj_id = internal_data['_id']
                if obj_id is None:
                    raise TypeError('"_id" is None for type {}'.format(
                        mapping.mapping_type))
                obj_key = (mapping.mapping_type, obj_id)
                self.objects[obj_key] = obj

            result.append(obj)
