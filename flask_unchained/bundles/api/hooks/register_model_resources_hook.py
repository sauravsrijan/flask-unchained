from flask_unchained import AppFactoryHook

from ..model_resource import ModelResource


class RegisterModelResourcesHook(AppFactoryHook):
    """
    Registers ModelResources and configures Serializers on them.
    """

    name = 'model_resources'
    bundle_module_names = ['views']
    bundle_override_module_names_attr = 'model_resources_module_names'
    run_after = ['models', 'serializers']

    def process_objects(self, app, objects):
        for resource_cls in objects.values():
            if isinstance(resource_cls.Meta.model, str):
                resource_cls.Meta.model = \
                    self.unchained.sqlalchemy_bundle.models[resource_cls.Meta.model]
            model_name = resource_cls.Meta.model.__name__

            self.attach_serializers_to_resource_cls(model_name, resource_cls)
            self.bundle.resources_by_model[model_name] = resource_cls

    def attach_serializers_to_resource_cls(self, model_name, resource_cls):
        try:
            serializer_cls = self.bundle.serializers_by_model[model_name]
        except KeyError:
            raise KeyError(f'No serializer found for the {model_name} model')

        if resource_cls.Meta.serializer is None:
            resource_cls.Meta.serializer = serializer_cls()

        if resource_cls.Meta.serializer_many is None:
            resource_cls.Meta.serializer_many = self.bundle.many_by_model.get(
                model_name, serializer_cls)(many=True)

        if resource_cls.Meta.serializer_create is None:
            resource_cls.Meta.serializer_create = self.bundle.create_by_model.get(
                model_name, serializer_cls)(context=dict(is_create=True))

    def type_check(self, obj):
        if not isinstance(obj, type):
            return False
        return issubclass(obj, ModelResource) and obj != ModelResource
