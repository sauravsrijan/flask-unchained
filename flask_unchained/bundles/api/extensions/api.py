from apispec.ext.marshmallow.openapi import __location_map__
from flask_unchained import FlaskUnchained, unchained
from flask_unchained import CREATE, DELETE, GET, LIST, PATCH, PUT
from flask_unchained.string_utils import title_case, pluralize

from ..apispec import APISpec
from ..model_resource import ModelResource


class Api:
    def __init__(self):
        self.app = None
        self.spec = None

    def init_app(self, app: FlaskUnchained):
        self.app = app

        extensions = getattr(app, 'extensions', {})
        extensions['api'] = self
        app.extensions = extensions

        self.spec = APISpec(app, plugins=app.config.get('API_APISPEC_PLUGINS'))

    def register_serializer(self, serializer, name=None, **kwargs):
        name = name or serializer.Meta.model.__name__
        self.spec.definition(name, schema=serializer, **kwargs)

    # FIXME need to be able to create 'fake' schemas for the query parameter
    def register_model_resource(self, resource: ModelResource):
        model_name = resource.model.__name__
        self.spec.add_tag({'name': model_name, 'description': resource.model.__doc__})

        for method in resource.methods():
            docs = {}
            http_method = method
            if method == CREATE:
                http_method = 'post'
                docs[http_method] = dict(
                    parameters=[
                        {'in': __location_map__['json'],
                         'required': True,
                         'schema': resource.serializer_create},
                    ],
                    responses={'201': dict(description=getattr(resource, CREATE).__doc__,
                                           schema=resource.serializer_create)})
            elif method == DELETE:
                docs[http_method] = dict(
                    parameters=[],
                    responses={'204': dict(description=getattr(resource, DELETE).__doc__)})
            elif method == GET:
                docs[http_method] = dict(
                    parameters=[],
                    responses={'200': dict(description=getattr(resource, GET).__doc__,
                                           schema=resource.serializer)})
            elif method == LIST:
                http_method = 'get'
                docs[http_method] = dict(
                    parameters=[],
                    responses={'200': dict(description=getattr(resource, LIST).__doc__,
                                           schema=resource.serializer_many)})
            elif method == PATCH:
                docs[http_method] = dict(
                    parameters=[
                        {'in': __location_map__['json'],
                         'required': False,
                         'schema': resource.serializer},
                    ],
                    responses={'200': dict(description=getattr(resource, PATCH).__doc__,
                                           schema=resource.serializer)})
            elif method == PUT:
                docs[http_method] = dict(
                    parameters=[
                        {'in': __location_map__['json'],
                         'required': True,
                         'schema': resource.serializer},
                    ],
                    responses={'200': dict(description=getattr(resource, PUT).__doc__,
                                           schema=resource.serializer)})

            docs[http_method]['tags'] = [model_name]
            route = unchained.controller_bundle.controller_endpoints[f'{resource.__name__}.{method}']

            display_name = title_case(model_name)
            if method == LIST:
                display_name = pluralize(display_name)
            docs[http_method]['summary'] = f'{http_method.upper()} {display_name}'

            for rule in self.app.url_map.iter_rules(route.endpoint):
                self.spec.add_path(app=self.app, rule=rule, operations=docs,
                                   view=route.view_func)

    def register_converter(self, converter, conv_type, conv_format=None, *, name=None):
        """Register custom path parameter converter
        :param BaseConverter converter: Converter
            Subclass of werkzeug's BaseConverter
        :param str conv_type: Parameter type
        :param str conv_format: Parameter format (optional)
        :param str name: Name of the converter. If not None, this name is used
            to register the converter in the Flask app.
            Example: ::
                api.register_converter(
                    UUIDConverter, 'string', 'UUID', name='uuid')
                @blp.route('/pets/{uuid:pet_id}')
                    ...
                api.register_blueprint(blp)
        This registers the converter in the Flask app and in the internal
        APISpec instance.
        Once the converter is registered, all paths using it will have
        corresponding path parameter documented with the right type and format.
        The `name` parameter need not be passed if the converter is already
        registered in the app, for instance if it belongs to a Flask extension
        that already registers it in the app.
        """
        if name:
            self.app.url_map.converters[name] = converter
        self.spec.register_converter(converter, conv_type, conv_format)

    def register_field(self, field, *args):
        """Register custom Marshmallow field
        Registering the Field class allows the Schema parser to set the proper
        type and format when documenting parameters from Schema fields.
        :param Field field: Marshmallow Field class
        ``*args`` can be:
        - a pair of the form ``(type, format)`` to map to
        - a core marshmallow field type (then that type's mapping is used)
        Examples: ::
            # Map to ('string', 'UUID')
            api.register_field(UUIDField, 'string', 'UUID')
            # Map to ('string')
            api.register_field(URLField, 'string', None)
            # Map to ('integer, 'int32')
            api.register_field(CustomIntegerField, ma.fields.Integer)
        """
        self.spec.register_field(field, *args)
