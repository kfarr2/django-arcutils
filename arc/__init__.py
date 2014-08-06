from django import forms
from django.template.loader import add_to_builtins
from django.contrib.admin.util import NestedObjects
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth import get_user_model
from django.conf import settings

# add the arc template tags to the builtin tags, and the bootstrap tag
add_to_builtins('arc.templatetags.arc')
add_to_builtins('bootstrapform.templatetags.bootstrap')

# monkey patch the PasswordResetForm so it indicates if a user does not exist
def _clean_email(self):
    email = self.cleaned_data['email']
    UserModel = get_user_model()
    if not UserModel.objects.filter(email=email, is_active=True).exists():
        raise forms.ValidationError("A user with that email address does not exist!")

    return email

PasswordResetForm.clean_email = _clean_email

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
