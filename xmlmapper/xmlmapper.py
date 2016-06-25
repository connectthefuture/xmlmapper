class XMLMapper:

    def __init__(self, mapping):
        self.mapping = mapping

    def load(self, xml, type_factory):
        raise NotImplementedError
