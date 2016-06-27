#xmlmapper
Simple library for mapping data from various xml sources to common data model.

#Mappings format

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

String in form `"[type: ]xpath"`, where xpath is an expression
that gets attribute value and type is either one of
built-in types (`string`, `bool`, `int`, `float`), `_type` of other
mapping (with `_id`) or name of filter passed to XMLMapper
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

#Mapping example

Two mappings

```json
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
```

If applied to following xml:

```xml
<r>
  <a id="1">
      <title>a1</title>
      <b>
          <id value="42"/>
      </b>
  </a>
  <c aid="1"/>
</r>
```

Will result in calls to object factory create method with argumens:

```python
('b', {'id': 42})
('a', {'title': 'a1', 'b_list': [b_obj_returned_by_first_call]})
('c', {'a': a_obj_returned_by_second_call})
```

#Usage
Create model factory by implementing `ModelFactory` interface. 
Construct `XMLMapper` with mappings list and your factory as arguments
and use its load or load_file method to parse data:
```python
class Factory(MapperObjectFactory):
    def create(self, object_type, fields):
        return (object_type, fields)
        
mapper = XMLMapper(
  [{
    '_type': 'a',
    '_match': '/a',
    'id': 'int: @id',
    'n': 'int: n',
  }], 
  Factory()
)

objects = mapper.load(b'<a id="10"><n>123</n></a>')
```
