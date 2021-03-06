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
            message += ' In element "{}" line {}.'.format(
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

    Mapping format

        Mapping is defined as python dict with some special keys

        `_type`: Name of object type, will be passed to object factory.
            Also can be used as value type to reference objects of this type.

        `_match`: XPath expression specifying what xml elements this
            mapping applies to. All other attributes are evaluated
            relatively to this element.

        `_id`: XPath expression returning string that will be used in other
            mapping to reference this object. May be ommited if current type
            is not used for references.

        Any other attribute is evaluated and, if its name doesn't start
        with '_', passed to object factory construction method.

        Attribute value can be in one of the following formats:

            String in form "[type: ]xpath", where xpath is an expression
                that gets attribute value and type is either one of
                built-in types (string, bool, int, float), _type of other
                mapping (with `id`) or name of filter passed to XMLMapper
                constructor. If other mapping type is uses result value
                will be and object (as returned by factory) with id
                determined by following xpath. If no type is specified
                string type is used.

            Another mapping. Will be applied to current element returning
                object as result. If no elements match None will be returned.
                Will throw XMLMapperLoadingError if more than one
                element matches.

            One-element list with another mapping. Mapping will be applied
                to current element returning list of objects.

        Example:
            Two mappings
            [{
                "_type": "a",
                "_match": "/r/a",
                "_id": "@id",
                "title": "title",
                "b_list": [{
                    "_type": "b",
                    "_match": "b",
                    "id": "int: id/@value"
                }]
            }, {
                "_type": "c",
                "_match": "/r/c",
                "a": "a: @aid",
            }]
            If applied to following xml:
            <r>
                <a id="1">
                    <title>a1</title>
                    <b>
                        <id value="42"/>
                    </b>
                </a>
                <c aid="1"/>
            </r>
            Will result in calls to object factory create method with argumens:
            ('b', {'id': 42})
            ('a', {'title': 'a1', 'b_list': [b_obj_returned_by_first_call]})
            ('c', {'a': a_obj_returned_by_second_call})
    """

    _RX_QUERY = re.compile(r'(?:(?P<type>\w+)\s*:\s*)?(?P<xpath>.*)')
    _VALUE_TYPES = {
        'string': str,
        'int': int,
        'float': float,
        'bool': lambda v: v is True or v.lower() == 'true',
    }

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
            str_value = self._get_string(element, self.xpath, value)
            if self.value_type == 'string':
                return str_value
            elif self.value_type in mapper._VALUE_TYPES:
                if str_value is None:
                    return None
                type_conv = mapper._VALUE_TYPES[self.value_type]
                try:
                    return type_conv(str_value)
                except ValueError:
                    raise XMLMapperLoadingError(
                        element,
                        'Invalid literal for {}: "{}".'.format(
                            self.value_type, str_value))
            elif self.value_type in mapper._filters:
                return mapper._filters[self.value_type](str_value)
            else:
                return state.get_object(element, self.value_type, str_value)

    class _MappingQuery(_Query):
        """Mapping query, either primary or nested."""
        def __init__(self, mapping_type, attr, match, has_id,
                     returns_list, compiled):
            XMLMapper._Query.__init__(self, mapping_type, attr)
            self.match, self.has_id = match, has_id
            self.returns_list, self.compiled = returns_list, compiled

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
            mappings: List of mapping specs to be applied in same order.
            filters: Dict of functions that can be used as custom value types
        """
        self._types = {}
        self._filters = filters or {}
        self._mappings = [self._compile_mapping(None, m) for m in mappings]

    def _compile_mapping(self, attr, mapping, returns_list=True):
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
                query = self._compile_mapping(k, v, False)
            elif isinstance(v, list) and len(v) == 1:
                query = self._compile_mapping(k, v[0], True)
            elif isinstance(v, six.string_types):
                query = self._compile_query(mtype, k, v)
            else:
                raise XMLMapperSyntaxError(
                    'Invalid query type {} for "{}" attribute '
                    'in type "{}"'.format(type(v), k, mtype))
            compiled.append(query)

        # Create mapping object and add it to types index
        query_obj = self._MappingQuery(mtype, attr, match, '_id' in mapping,
                                       returns_list, compiled)
        self._types[mtype] = query_obj
        return query_obj

    def _compile_xpath(self, xpath):
        return etree.XPath(xpath, smart_strings=False)

    def _compile_query(self, mapping_type, attr, query):
        """Parses and compiles attribute query spec ([type:] xpath)"""
        q_match = self._RX_QUERY.match(query)
        assert q_match  # should always match since it has .*

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

        if not mapping.returns_list:
            if len(objects) == 0:
                return None
            elif len(objects) == 1:
                return objects[0]
            else:
                raise XMLMapperLoadingError(
                    element,
                    'Nested mapping returned more than one '
                    'object ({}).'.format(len(objects)))
        return objects
