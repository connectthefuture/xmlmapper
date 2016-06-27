import six

from xmlmapper import MapperObjectFactory

from app.models import Event, Place, Session, Tag, Image, Person, Membership


class ModelsFactory(MapperObjectFactory):
    MODELS = {
        'event': Event,
        'place': Place,
        'session': Session,
        'event_tag': Tag,
        'place_tag': Tag,
        'event_image': Image,
        'place_image': Image,
        'person': Person,
        'place_person': Membership,
    }

    def create(self, model_type, fields):
        # Django model has to be saved before its m2m relations
        # can be used so separating those
        regular_fields = {}
        m2m_fields = {}
        for k, v in six.iteritems(fields):
            if k.startswith('#'):
                m2m_fields[k[1:]] = v
            else:
                regular_fields[k] = v
        obj, _ = self.MODELS[model_type].objects.get_or_create(
            **regular_fields)
        for k, v in six.iteritems(m2m_fields):
            attr = getattr(obj, k)
            for x in v:
                attr.add(x)
        return obj
