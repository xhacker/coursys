from django.core.urlresolvers import reverse
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.http import HttpResponseRedirect
from django.utils.http import urlquote
from coredata.models import Person, Role
import datetime

PRIVACY_VERSION = 1

# Who has to sign the Privacy statement?
RELEVANT_ROLES = ['ADVS', 'ADMN', 'TAAD', 'GRAD', 'GRPD', 'FUND']

def set_privacy_signed(person):
    person.config["privacy_signed"] = True
    person.config["privacy_date"] = datetime.date.today()
    person.config["privacy_version"] = PRIVACY_VERSION 
    person.save()

def needs_privacy_signature(request, only_relevant_roles=False):
    """
    Decide if the user needs to see the privacy agreement.

    only_relevant_roles will show the user the agreement only if they have a Role that needs to agree: used in the
    generic @requires_role decorator. Default behaviour is if we called this, then they need to agree.
    """
    try:
        you = Person.objects.get(userid=request.user.username)
    except Person.DoesNotExist:
        return False # non-Person can't have a role to worry about

    if 'privacy_signed' in you.config and you.config['privacy_signed']:
        return False

    if only_relevant_roles:
        roles = Role.objects.filter(person__userid=request.user.username,
                                role__in=RELEVANT_ROLES)
        return roles.exists()
    else:
        return True


def privacy_redirect(request):
    """
    Build the redirect response to give a user that needs to agree
    """
    privacy_url = reverse('privacy.views.privacy')
    path = '%s?%s=%s' % (privacy_url, REDIRECT_FIELD_NAME,
                         urlquote(request.get_full_path()))
    return HttpResponseRedirect(path)