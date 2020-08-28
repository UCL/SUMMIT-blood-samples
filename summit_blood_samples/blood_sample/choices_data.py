from .models import STATECHOICE, SITECHOICE, VISITCHOICE, \
    PROCESSING_STATUS, SAMPLE_TYPE, SITE_HELD

# Import default choices from models
state_status = dict(STATECHOICE)
state_status = {str(k): v for k, v in state_status.items()}

site_choices = dict(SITECHOICE)
site_choices = {str(k): v for k, v in site_choices.items()}

visit_choices = dict(VISITCHOICE)
visit_choices = {str(k): v for k, v in visit_choices.items()}

processing_status = dict(PROCESSING_STATUS)
processing_status = {str(k): v for k, v in processing_status.items()}

sample_type = dict(SAMPLE_TYPE)
sample_type = {str(k): v for k, v in sample_type.items()}

site_held_choices = dict(SITE_HELD)
site_held_choices = {str(k): v for k, v in site_held_choices.items()}
