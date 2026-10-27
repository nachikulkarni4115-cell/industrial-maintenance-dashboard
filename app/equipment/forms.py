from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, SubmitField, DateField
from wtforms.validators import DataRequired, Length, Optional
from app.models import Equipment


class EquipmentForm(FlaskForm):
    asset_tag = StringField("Asset Tag", validators=[DataRequired(), Length(1, 64)])
    name = StringField("Name", validators=[DataRequired(), Length(1, 120)])
    equipment_type = SelectField("Type", choices=[(t, t.title()) for t in Equipment.EQUIPMENT_TYPES], validators=[DataRequired()])
    location = StringField("Location", validators=[Optional(), Length(0, 200)])
    criticality = SelectField("Criticality", choices=[(c, c.title()) for c in Equipment.CRITICALITIES], default="medium")
    status = SelectField("Status", choices=[(s, s.replace("_", " ").title()) for s in Equipment.STATUSES], default="operational")
    manufacturer = StringField("Manufacturer", validators=[Optional(), Length(0, 100)])
    model = StringField("Model", validators=[Optional(), Length(0, 100)])
    install_date = DateField("Install Date", validators=[Optional()])
    notes = TextAreaField("Notes", validators=[Optional()])
    submit = SubmitField("Save")
