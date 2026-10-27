from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DateField, SubmitField
from wtforms.validators import DataRequired, Length, Optional
from app.models import WorkOrder


class WorkOrderForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(1, 200)])
    description = TextAreaField("Description", validators=[Optional()])
    priority = SelectField("Priority", choices=[(p, p.title()) for p in WorkOrder.PRIORITIES], default="medium")
    assigned_to = StringField("Assigned To", validators=[Optional(), Length(0, 100)])
    due_date = DateField("Due Date", validators=[Optional()])
    submit = SubmitField("Save")


class WorkOrderStatusForm(FlaskForm):
    status = SelectField("Status", choices=[(s, s.replace("_", " ").title()) for s in WorkOrder.STATUSES])
    completion_notes = TextAreaField("Completion / Update Notes", validators=[Optional()])
    submit = SubmitField("Update Status")
