from flask_unchained import AppFactoryHook, FlaskUnchained
from typing import *

from ..object_types import MutationsObjectType


class RegisterGrapheneMutationsHook(AppFactoryHook):
    name = 'graphene_mutations'
    bundle_module_names = ['graphql.schema']
    bundle_override_module_names_attr = 'graphene_mutations_module_names'
    run_after = ['graphene_types']

    # skipcq: PYL-W0221 (parameters mismatch in overridden method)
    def process_objects(self,
                        app: FlaskUnchained,
                        mutations: Dict[str, MutationsObjectType]):
        self.bundle.mutations = mutations

    def type_check(self, obj: Any):
        is_subclass = isinstance(obj, type) and issubclass(obj, MutationsObjectType)
        return is_subclass and obj != MutationsObjectType and (
                not hasattr(obj, 'Meta') or not getattr(obj.Meta, 'abstract', False))
