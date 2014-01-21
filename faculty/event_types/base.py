from django import forms
from django.template import Context, Template
from coredata.models import Role
import datetime, itertools

PERMISSION_CHOICES = { # who can create/edit/approve various things?
        'MEMB': 'Faculty Member',
        'DEPT': 'Department',
        'FAC': 'Dean\'s Office',
        }
PERMISSION_LEVEL = {
        'NONE': 0,
        'MEMB': 1,
        'DEPT': 2,
        'FAC': 3,
        }


class BaseEntryForm(forms.Form):
    # TODO: should this be a ModelForm for a CareerEvent? We'll have a circular import if so.
    title = forms.CharField(max_length=80, required=True)
    start_date = forms.DateField()
    end_date = forms.DateField()


class CareerEventHandlerBase(object):
    # type configuration stuff: override as necessary
    is_instant = False # set to True for events that have no duration
    exclusion_category = None # if set, only one CareerEvent with this exclusion_category
                              # can exist for a faculty member at a given time.
    date_bias = 'DATE' # or 'SEM': which interface widget should be presented to default in the form?
    affects_teaching = False # events of this type might affect teaching credits/load
    affects_salary = False   # events of this type might affect salary/pay

    viewable_by = 'MEMB'
    editable_by = 'DEPT'
    approval_by = 'FAC'
    
    
    # basic functionality: hopefully don't have to override
    
    def __init__(self, faculty=None, event=None):
        """
        faculty: a coredata.Person representing the faculty member in question.
        event: the CareerEvent we're manipulating, if it exists.
        """
        self.event = event
        if event and faculty:
            assert event.person == faculty

        if faculty:
            self.faculty = faculty
        elif event and event.person:
            self.faculty = event.person
        else:
            raise ValueError, "A CareerEventType must know which faculty member it's dealing with."


    def permission(self, editor):
        """
        This editor's permission level with respect to this faculty member.
        """
        edit_units = set(r.unit for r in Role.objects.filter(person=editor, role='ADMN'))
        fac_units = set(r.unit for r in Role.objects.filter(person=self.faculty, role='FAC'))
        super_units = set(itertools.chain(*(u.super_units() for u in fac_units)))

        if editor == self.faculty:
            # first on purpose: don't let dept chairs approve/edit their own stuff
            return 'MEMB'
        elif edit_units & super_units:
            # give dean's office level permission to anybody above in the hierarchy:
            # not technically correct, but correct in practice.
            return 'FAC'
        elif edit_units & fac_units:
            return 'DEPT'
        else:
            return 'NONE'

        
    def has_permission(self, perm, editor):
        """
        Does the given editor (a coredata.Person) have this permission
        for this faculty member?
        
        Implemented as a method so we can override or extend if necessary.
        """
        permission = self.permission(editor)
        return PERMISSION_LEVEL[permission] >= PERMISSION_LEVEL[perm]

    def can_view(self, editor):
        """
        Can the given user (a coredata.Person) can view the
        CareerEventType for this faculty member?
        """
        return self.has_permission(self.viewable_by, editor)
            
    def can_edit(self, editor):
        """
        Can the given editor (a coredata.Person) can create/edit this
        CareerEventType for this faculty member?
        """
        return self.has_permission(self.editable_by, editor)

    def can_approve(self, editor):
        """
        Can the given editor (a coredata.Person) can approve this
        CareerEventType for this faculty member?
        """
        return self.has_permission(self.approval_by, editor)
            

    # maybe override? Hopefully we can avoid and use this as-is.

    def get_entry_form(self):
        """
        Return a Django Form that can be used to create/edit a CareerEvent
        """
        initial = {'title': self.default_title, 'start_date': datetime.date.today()}
        f = self.EntryForm(initial=initial)

        if self.is_instant and 'end_date' in f.fields:
            del f.fields['end_date']

        return f

    def to_html(self):
        """
        A detailed HTML presentation of this event
        """
        if not self.event:
            raise ValueError, "Handler must have its 'event' set to be converted to HTML."

        t = Template(self.TO_HTML_TEMPLATE)
        c = Context({'event': self.event, 'handler': self, 'faculty': self.faculty})
        return t.render(c)


    # type-specific stuff that probably need to be overridden.
    
    class EntryForm(BaseEntryForm):
        pass

    @property
    def default_title(self):
        return 'Some Career Event'

    def to_career_event(self, form):
        """
        Given an EntryForm instance, return the corresponding CareerEvent instance
        (~= inverse of get_entry_form)
        """
        # TODO: can we be general enough here to actually have common logic here?
        # if self.event:
        #     should modify and return that
        raise NotImplementedError

    def short_summary(self):
        """
        A short-line text-only summary of the event for summary displays
        """
        raise NotImplementedError


    def get_salary(self, prev_salary):
        """
        Calculate salary with this CareerEvent taken into account: salary was prev_salary argument, and this
        returns the salary after this event has happened.

        Must be implemented iff self.affects_salary.
        """
        raise NotImplementedError

    def get_teaching_balance(self, prev_teaching):
        """
        Calculate number of courses that must be taught with this CareerEvent taken into account: courses required
        was prev_teaching argument, and this returns the balance after this event has happened.

        Must be implemented iff self.affects_teaching.
        """
        raise NotImplementedError