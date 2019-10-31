import importlib
import inspect
import os
import sys

from types import FunctionType, ModuleType
from typing import *

from py_meta_utils import Singleton

from .bundles import AppBundle, Bundle
from .constants import DEV, PROD, STAGING, TEST
from .exceptions import BundleNotFoundError
from .flask_unchained import FlaskUnchained
from .unchained import unchained
from .utils import cwd_import


def maybe_set_app_factory_from_env():
    app_factory = os.getenv('UNCHAINED_APP_FACTORY', None)
    if app_factory:
        module_name, class_name = app_factory.rsplit('.', 1)
        app_factory_cls = getattr(cwd_import(module_name), class_name)
        AppFactory.set_singleton_class(app_factory_cls)


class AppFactory(metaclass=Singleton):
    """
    This class implements the `Application Factory Pattern`_ for Flask Unchained.

    .. _Application Factory Pattern: http://flask.pocoo.org/docs/1.0/patterns/appfactories/
    """

    APP_CLASS = FlaskUnchained
    """
    Set :attr:`APP_CLASS` to use a custom subclass of
    :class:`~flask_unchained.FlaskUnchained`.
    """

    REQUIRED_BUNDLES = [
        'flask_unchained.bundles.babel',
        'flask_unchained.bundles.controller',
    ]

    def create_app(self,
                   env: Union[DEV, PROD, STAGING, TEST],
                   bundles: Optional[List[str]] = None,
                   *,
                   _config_overrides: Optional[Dict[str, Any]] = None,
                   **app_kwargs,
                   ) -> FlaskUnchained:
        """
        Flask Unchained Application Factory. Returns an instance of
        :attr:`APP_CLASS` (by default, :class:`~flask_unchained.FlaskUnchained`).

        Example Usage::

            app = AppFactory().create_app(PROD)

        :param env: Which environment the app should run in. Should be one of
                    "development", "production", "staging", or "test" (you can import
                    them: ``from flask_unchained import DEV, PROD, STAGING, TEST``)
        :param bundles: An optional list of bundle modules names to use. Overrides
                        ``unchained_config.BUNDLES`` (mainly useful for testing).
        :param app_kwargs: keyword argument overrides for the :attr:`APP_CLASS`
                           constructor
        :param _config_overrides: a dictionary of config option overrides; meant for
                                  test fixtures.
        :return: The configured and initialized :attr:`APP_CLASS` application instance
        """
        unchained_config = self.load_unchained_config(env)
        app_bundle, bundles = self.load_bundles(
            bundle_package_names=bundles or getattr(unchained_config, 'BUNDLES', []),
            unchained_config=unchained_config,
        )

        # this is for developing standalone bundles (as opposed to regular apps)
        if app_bundle is None and env != TEST:
            app_kwargs['template_folder'] = os.path.join(
                os.path.dirname(__file__), 'templates')

        # set kwargs to pass to Flask from the unchained_config
        valid_app_kwargs = {
            name for i, (name, param)
            in enumerate(inspect.signature(self.APP_CLASS).parameters.items())
            if i > 0 and (
                    param.kind == param.POSITIONAL_OR_KEYWORD
                    or param.kind == param.KEYWORD_ONLY
            )
        }
        for kw in valid_app_kwargs:
            config_key = kw.upper()
            if hasattr(unchained_config, config_key):
                app_kwargs.setdefault(kw, getattr(unchained_config, config_key))

        # set up the root static/templates folders (if any)
        root_path = app_kwargs.get('root_path')
        if not root_path and bundles:
            root_path = bundles[-1].root_path
            if not bundles[-1].is_single_module:
                root_path = os.path.dirname(root_path)
            app_kwargs['root_path'] = root_path

        def root_folder_or_none(folder_name):
            if not root_path:
                return None
            folder = os.path.join(root_path, folder_name)
            return folder if os.path.isdir(folder) else None

        if 'template_folder' not in app_kwargs:
            app_kwargs.setdefault('template_folder', root_folder_or_none('templates'))

        if 'static_folder' not in app_kwargs:
            app_kwargs.setdefault('static_folder', root_folder_or_none('static'))

        if app_kwargs['static_folder'] and not app_kwargs.get('static_url_path'):
            app_kwargs.setdefault('static_url_path', '/static')

        # instantiate the app
        app_import_name = (bundles[-1].module_name.split('.')[0] if bundles
                           else ('tests' if env == TEST else 'dev_app'))
        app = self.APP_CLASS(app_import_name, **app_kwargs)

        # and boot up Flask Unchained
        if not root_path and bundles and not bundles[-1].is_single_module:
            # Flask assumes the root_path is based on the app_import_name, but
            # we want it to be the project root, not the app bundle root
            app.root_path = os.path.dirname(app.root_path)
            app.static_folder = app_kwargs['static_folder']

        for bundle in bundles:
            bundle.before_init_app(app)

        unchained.init_app(app, env, bundles, _config_overrides=_config_overrides)

        for bundle in bundles:
            bundle.after_init_app(app)

        return app

    @staticmethod
    def load_unchained_config(env: Union[DEV, PROD, STAGING, TEST]) -> ModuleType:
        if not sys.path or sys.path[0] != os.getcwd():
            sys.path.insert(0, os.getcwd())

        msg = None
        if env == TEST:
            try:
                return cwd_import('tests._unchained_config')
            except ImportError as e:
                msg = f'{e.msg}: Could not find _unchained_config.py in the tests directory'

        unchained_config_module_name = os.getenv('UNCHAINED_CONFIG', 'unchained_config')
        try:
            return cwd_import(unchained_config_module_name)
        except ImportError as e:
            if not msg:
                msg = f'{e.msg}: Could not find {unchained_config_module_name}.py ' \
                      f'in the current working directory (are you in the project root?)'
            e.msg = msg
            raise e

    @classmethod
    def load_bundles(cls,
                     bundle_package_names: Optional[List[str]] = None,
                     unchained_config: Optional[ModuleType] = None,
                     ) -> Tuple[Union[None, AppBundle], List[Bundle]]:
        bundle_package_names = bundle_package_names or []
        for b in cls.REQUIRED_BUNDLES:
            if b not in bundle_package_names:
                bundle_package_names.insert(0, b)

        if not bundle_package_names:
            return None, []

        bundles = []
        for bundle_package_name in bundle_package_names:
            bundles.append(cls.load_bundle(bundle_package_name))

        if not isinstance(bundles[-1], AppBundle):
            if unchained_config:
                single_module_app_bundle = cls._bundle_from_module(unchained_config)
                if single_module_app_bundle:
                    bundles.append(single_module_app_bundle)
                return single_module_app_bundle, bundles
            return None, bundles
        return bundles[-1], bundles

    @classmethod
    def load_bundle(cls, bundle_package_name: str) -> Union[AppBundle, Bundle]:
        for module_name in [f'{bundle_package_name}.bundle', bundle_package_name]:
            try:
                module = importlib.import_module(module_name)
            except ImportError as e:
                if f"No module named '{module_name}'" in str(e):
                    continue
                raise e

            bundle = cls._bundle_from_module(module)
            if bundle:
                return bundle

        raise BundleNotFoundError(
            f'Unable to find a Bundle subclass in the {bundle_package_name} bundle!'
            ' Please make sure this bundle is installed and that there is a Bundle'
            ' subclass in the packages\'s __init__.py (or bundle.py) file.')

    @classmethod
    def is_bundle(cls, module: ModuleType) -> FunctionType:
        def _is_bundle(obj):
            return (
                isinstance(obj, type) and issubclass(obj, Bundle)
                and obj not in {AppBundle, Bundle}
                and obj.__module__.startswith(module.__name__)
            )
        return _is_bundle

    @classmethod
    def _bundle_from_module(cls, module: ModuleType) -> Union[AppBundle, Bundle, None]:
        try:
            bundle_class = inspect.getmembers(module, cls.is_bundle(module))[0][1]
        except IndexError:
            return None
        else:
            return bundle_class()


__all__ = [
    'AppFactory',
    'maybe_set_app_factory_from_env',
]
