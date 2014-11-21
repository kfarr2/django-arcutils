from __future__ import print_function
from __future__ import absolute_import
import random, datetime
import logging
from django import forms
from django.forms.fields import Field
from django.forms.models import BaseModelFormSet
from django.forms.formsets import BaseFormSet
from django.forms.util import ErrorDict
from django.template import add_to_builtins
from django.contrib.admin.util import NestedObjects
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.signals import request_started
from django.dispatch import receiver
from django.utils.importlib import import_module
from django.utils.six import add_metaclass

logger = logging.getLogger(__name__)

# set the default place to send logs
LOGSTASH_ADDRESS = getattr(settings, "LOGSTASH_ADDRESS", 'logs.rc.pdx.edu:8000')
# set the default probability of when to clear sessions
CLEAR_SESSIONS_PROBABILITY = getattr(settings, "CLEAR_SESSIONS_PROBABILITY", 0.01)

forms.Form.required_css_class = "required"
forms.ModelForm.required_css_class = "required"
Field.required_css_class = "required"

add_to_builtins('django.contrib.staticfiles.templatetags.staticfiles')
# add the arc template tags to the builtin tags, and the bootstrap tag
add_to_builtins('arcutils.templatetags.arc')
add_to_builtins('arcutils.templatetags.bootstrap')


# add some helpful methods to the formset
class FormSetMixin(object):
    def iter_with_empty_form_first(self):
        """
        Iterates over the forms in this formset, but the first form yielded
        is the empty one. This simplifies the logic in templates, since the
        empty_form is no longer a special case
        """
        yield self.empty_form
        for form in iter(self):
            yield form

    def clean(self):
        """
        When cleaning, if the form is being deleted, any errors on it should be
        ignored
        """
        for form in self.forms:
            # this form is being deleted, so overwrite the errors
            if form.cleaned_data.get("DELETE"):
                form._errors = ErrorDict()


# add the FormSetMixin to the base FormSet classes
class BaseFormSet(FormSetMixin, BaseFormSet): pass
class BaseModelFormSet(FormSetMixin, BaseModelFormSet): pass


# monkey patch the PasswordResetForm so it indicates if a user does not exist
def _clean_email(self):
    email = self.cleaned_data['email']
    UserModel = get_user_model()
    if not UserModel.objects.filter(email=email, is_active=True).exists():
        raise forms.ValidationError("A user with that email address does not exist!")

    return email

PasswordResetForm.clean_email = _clean_email


def dictfetchall(cursor):
    "Returns all rows from a cursor as a dict"
    desc = cursor.description
    return [
        dict(zip([col[0] for col in desc], row))
        for row in cursor.fetchall()
    ]


def will_be_deleted_with(obj):
    """
    Pass in any Django model object that you intend to delete.
    This will iterate over all the model classes that would be affected by the
    deletion, yielding a two-tuple: the model class, and a set of all the
    objects of that type that would be deleted.
    """
    collector = NestedObjects(using="default")
    collector.collect([obj])
    # the collector returns a list of all objects in the database that
    # would be deleted if `obj` were deleted.
    for cls, list_of_items_to_be_deleted in collector.data.items():
        # remove obj itself from the list
        if cls == obj.__class__:
            list_of_items_to_be_deleted = set(item for item in list_of_items_to_be_deleted if item.pk != obj.pk)
            if len(list_of_items_to_be_deleted) == 0:
                continue

        yield cls, list_of_items_to_be_deleted


class IterableChoiceEnum(type):

    def __init__(cls, name, bases, attrs):
        cls._choices_dict = dict(cls)

    def __iter__(cls):
        """Simply return the iterator of the _choices tuple"""
        return iter(cls._choices)

    def __getitem__(cls, choice):
        """Return choice description via item access.

        Example::

            >>> class MyEnum(ChoiceEnum):
            ...
            ...     A = 1
            ...     B = 2
            ...
            ...     _choices = (
            ...         (A, 'Alpha'),
            ...         (B, 'Beta'),
            ...     )
            ...
            >>> MyEnum[MyEnum.A]
            'Alpha'

        """
        return cls._choices_dict[choice]

    def get(cls, choice, default=None):
        try:
            return cls[choice]
        except KeyError:
            return default


@add_metaclass(IterableChoiceEnum)
class ChoiceEnum(object):
    """
    This creates an iterable *class* (as opposed to an iterable *instance* of a
    class). Subclasses must define a class variable called `_choices` which is a
    list of 2-tuples. Subclasses can be passed directly to a field as the
    `choice` kwarg.

    For example:

    class FooType(ChoiceEnum):
        A = 1
        B = 2

        _choices = (
            (A, "Alpha"),
            (B, "Beta"),
        )


    class SomeModel(models.Model):
        foo = models.ChoiceField(choices=FooType)
    """
    _choices = ()
    # http://stackoverflow.com/questions/5434401/python-is-it-possible-to-make-a-class-iterable-using-the-standard-syntax


if "django.contrib.sessions" in settings.INSTALLED_APPS:
    @receiver(request_started)
    def session_monitor(sender, **kwargs):
        if random.random() <= CLEAR_SESSIONS_PROBABILITY:
            engine = import_module(settings.SESSION_ENGINE)
            try:
                engine.SessionStore.clear_expired()
                logger.debug("Sessions cleared")
            except NotImplementedError:
                logger.debug("Session engine '%s' doesn't support clearing "
                        "expired sessions." % settings.SESSION_ENGINE)
