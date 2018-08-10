import flask_unchained
import os
import sys

from babel.messages.frontend import CommandLineInterface
from flask import current_app
from flask_unchained.cli import cli, click
from flask_unchained import AppBundle

DEFAULT_DOMAIN = 'messages'


@cli.group()
def babel():
    """
    Babel translations commands.
    """


@babel.command()
@click.option('--domain', '-d', default=DEFAULT_DOMAIN)
def extract(domain):
    """
    Extract newly added translations keys from source code.
    """
    translations_dir = _get_translations_dir()
    domain = _get_translations_domain(domain)
    babel_cfg = _get_babel_cfg()
    pot = os.path.join(translations_dir, f'{domain}.pot')
    return _run(f'extract -F {babel_cfg} -o {pot} .')


@babel.command()
@click.argument('lang', help='The language code to initialize translations for.')
@click.option('--domain', '-d', default=DEFAULT_DOMAIN)
def init(lang, domain):
    """
    Initialize translations for a language code.
    """
    translations_dir = _get_translations_dir()
    domain = _get_translations_domain(domain)
    pot = os.path.join(translations_dir, f'{domain}.pot')
    return _run(f'init -i {pot} -d {translations_dir} -l {lang}')


@babel.command()
@click.option('--domain', '-d', default=DEFAULT_DOMAIN)
def compile(domain):
    """
    Compile translations into a distributable ``.mo`` file.
    """
    translations_dir = _get_translations_dir()
    domain = _get_translations_domain(domain)
    return _run(f'compile --directory={translations_dir} --domain={domain}')


@babel.command()
@click.option('--domain', '-d', default=DEFAULT_DOMAIN)
def update(domain):
    """
    Update language-specific translations files with new keys discovered by
    ``flask babel extract``.
    """
    translations_dir = _get_translations_dir()
    domain = _get_translations_domain(domain)
    pot = os.path.join(translations_dir, f'{domain}.pot')
    return _run(f'update -i {pot} -d {translations_dir} --domain={domain}')


def _run(str):
    return CommandLineInterface().run([sys.argv[0]] + str.split(' '))


def _get_babel_cfg():
    app_bundle = list(current_app.unchained.bundles.values())[-1]
    app_babel_cfg = os.path.join(app_bundle.root_folder, 'babel.cfg')
    if os.path.exists(app_babel_cfg):
        return app_babel_cfg

    # default to using flask_unchained's babel.cfg
    return os.path.join(
        os.path.abspath(os.path.dirname(os.path.dirname(flask_unchained.__file__))),
        'babel.cfg')


def _get_translations_dir():
    app_bundle = list(current_app.unchained.bundles.values())[-1]
    is_user_app = isinstance(app_bundle, AppBundle)

    root_dir = app_bundle.root_folder if is_user_app else app_bundle.folder
    translations_dir = os.path.join(root_dir, 'translations')
    if not os.path.exists(translations_dir):
        os.makedirs(translations_dir, exist_ok=True)

    return translations_dir


def _get_translations_domain(domain):
    if domain != DEFAULT_DOMAIN:
        return domain

    app_bundle = list(current_app.unchained.bundles.values())[-1]
    if isinstance(app_bundle, AppBundle):
        return DEFAULT_DOMAIN

    return app_bundle.module_name
