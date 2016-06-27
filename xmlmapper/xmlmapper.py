import re
from io import BytesIO

import six
from lxml import etree


class XMLMapperError(Exception):
    """Main exception base class for xmlmapper.  All other exceptions inherit
    from this one."""
    pass


class XMLMapperSyntaxError(XMLMapperError, SyntaxError):
    """Error compiling mapping spec."""
    pass


class XMLMapperLoadingError(XMLMapperError, RuntimeError):
    """Error during mapping process

    Note:
        Stores tag and line number of element which attributes
        were processed, not of the attribute itself.

    Attributes:
        element_tag (str): XML tag of element
        source_line (int): Line number of element in xml source
    """

    def __init__(self, element, message):
        if element is not None:
            message += 'In element "{}" line {}.'.format(
                element.tag, element.sourceline)
        super(XMLMapperLoadingError, self).__init__(message)
        self.element_tag = element.tag
        self.source_line = element.sourceline


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

        def _get_string(self, element, xpath_query, value):
            if isinstance(value, list):
                if len(value) == 0:
                    return None
                if len(value) > 1:
                    raise XMLMapperLoadingError(
                        element,
                        'XPath "{}" returned multiple elements while single '
                        'value was expected.'.format(xpath_query))
                value = value[0]
                if hasattr(value, 'text'):
                    value = value.text
            return six.text_type(value).strip()

        def run(self, mapper, state, element, object_factory, result):
            value = self.xpath(element)
            if self.value_type == 'string':
                return self._get_string(element, self.xpath, value)
            elif self.value_type == 'int':
                str_value = self._get_string(element, self.xpath, value)
                if str_value is None:
                    return None
                try:
                    return int(str_value)
                except ValueError:
                    raise XMLMapperLoadingError(
                        element,
                        'Invalid literal for int: "{}".'.format(str_value))
            elif self.value_type in mapper._filters:
                str_value = self._get_string(element, self.xpath, value)
                return mapper._filters[self.value_type](str_value)
            else:
                obj_id = self._get_string(element, self.xpath, value)
                return state.get_object(element, self.value_type, obj_id)

    class _MappingQuery(_Query):
        """Mapping query, either primary or nested."""
        def __init__(self, mapping_type, attr, match, has_id, compiled):
            XMLMapper._Query.__init__(self, mapping_type, attr)
            self.match, self.has_id, self.compiled = match, has_id, compiled

        def run(self, mapper, state, element, object_factory, result):
            return mapper._load_mapping(state, element, self,
                                        object_factory, result)

    class _State:
        """Stores loaded objects while mapping."""
        def __init__(self):
            self._objects = {}

        def add_object(self, element, obj_type, obj_id, obj):
            if obj_id is None:
                raise XMLMapperLoadingError(
                    element,
                    '"_id" is None for type "{}".'.format(obj_type))

            obj_key = (obj_type, obj_id)
            if obj_key in self._objects:
                raise XMLMapperLoadingError(
                    element,
                    'Duplicate object with id "{}" '
                    'for type "{}"'.format(obj_id, obj_type))

            self._objects[obj_key] = obj

        def get_object(self, element, obj_type, obj_id):
            obj_key = (obj_type, obj_id)
            if obj_key not in self._objects:
                raise XMLMapperLoadingError(
                    element,
                    'Referenced undefined "{}" object with '
                    'id "{}".'.format(obj_type, obj_id))
            return self._objects[obj_key]

    def __init__(self, mappings, filters=None):
        """Creates new mapper for provided spec.

        Args:
            mappings: List of mapping specs.
            filters: Dict of functions that can be used as custom value types
        """
        self._types = {}
        self._filters = filters or {}
        self._mappings = [self._compile_mapping(None, m) for m in mappings]

    def _compile_mapping(self, attr, mapping, parent=None):
        # Parses and compiles mapping spec (dict)
        # Required attributes: _type, _match
        if '_type' not in mapping:
            raise XMLMapperSyntaxError('Missing required "_type" attribute')
        mtype = mapping['_type']
        if not isinstance(mtype, six.string_types):
            raise XMLMapperSyntaxError('"_type" should be a string')
        if '_match' not in mapping:
            raise XMLMapperSyntaxError(
                'Missing required "_match" attribute '
                'for type {}'.format(mtype))
        if mtype in self._types:
            raise XMLMapperSyntaxError(
                'Duplicate mapping type "{}"'.format(mtype))

        if not isinstance(mapping['_match'], six.string_types):
            raise XMLMapperSyntaxError(
                '"_match" should be a string in type "{}"'.format(mtype))
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
                raise XMLMapperSyntaxError(
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
        """Parses and compiles attribute query spec ([type:] xpath)"""
        q_match = self._RX_QUERY.match(query)

        if not q_match:
            raise XMLMapperSyntaxError(
                'Invalid query format: {}'.format(query))

        q_type = q_match.group('type')
        if q_type is None:
            q_type = 'string'

        if q_type not in self._VALUE_TYPES and q_type not in self._filters:
            if q_type not in self._types:
                raise XMLMapperSyntaxError(
                    'Unknown value type "{}" for "{}" attribute '
                    'in type "{}"'.format(q_type, attr, mapping_type))
            elif not self._types[q_type].has_id:
                raise XMLMapperSyntaxError(
                    'Invalid value type "{}" for "{}" attribute '
                    'in type "{}" (only types with "_id" can be '
                    'referenced)'.format(q_type, attr, mapping_type))

        if attr == '_id' and q_type != 'string':
            raise XMLMapperSyntaxError(
                'In type "{}" attribute "_id" is required '
                'to be a string.'.format(mapping_type))

        q_xpath = self._compile_xpath(q_match.group('xpath'))
        return self._XPathQuery(mapping_type, attr, q_type, q_xpath)

    def load(self, xml, object_factory):
        """Parse XML bytes and load objects according to spec.

        Args:
            xml: binary string (bytes) containing XML.
            object_factory: `MapperObjectFactory` for creating objects.

        Returns:
            List of loaded objects as returned by `object_factory`.
        """
        return self.load_file(BytesIO(xml), object_factory)

    def load_file(self, xml_file, object_factory):
        """Parse XML file and load objects according to spec.

        Args:
            xml: file, file-like object, filename or url to get XML from.
            object_factory: `MapperObjectFactory` for creating objects.

        Returns:
            List of loaded objects as returned by `object_factory`.
        """
        parser = etree.XMLParser(remove_blank_text=True)
        root = etree.parse(xml_file, parser)
        result = []
        state = self._State()
        for mapping in self._mappings:
            self._load_mapping(state, root, mapping, object_factory, result)
        return result

    def _load_mapping(self, state, element, mapping, object_factory, result):
        """Matches mapping and processes its attributes"""
        objects = []
        for match_el in mapping.match(element):
            # load attributes
            internal_data = {}
            data = {}
            for query in mapping.compiled:
                value = query.run(self, state, match_el,
                                  object_factory, result)
                if query.attr.startswith('_'):
                    internal_data[query.attr] = value
                else:
                    data[query.attr] = value

            obj = object_factory.create(mapping.mapping_type, data)
            objects.append(obj)
            result.append(obj)

            # add object to index if necessary
            if mapping.has_id:
                assert '_id' in internal_data
                state.add_object(
                    match_el, mapping.mapping_type, internal_data['_id'], obj)

        return objects
