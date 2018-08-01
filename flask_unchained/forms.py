from flask_wtf import FlaskForm as BaseForm


class FlaskForm(BaseForm):
    field_order = ()

    def __iter__(self):
        if not self.field_order:
            return super().__iter__()
        return iter([field for name, field in self._fields.items()
                     if name not in self.field_order]
                    + [self._fields[f] for f in self.field_order])