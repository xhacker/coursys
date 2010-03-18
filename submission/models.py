from django.db import models
from grades.models import Activity
from coredata.models import Member, Person,CourseOffering
#from courses.grades.models import slug
from groups.models import Group,GroupMember
from datetime import datetime
from autoslug import AutoSlugField
from django.shortcuts import get_object_or_404


STATUS_CHOICES = [
    ('NEW', 'New'),
    ('INP', 'In-Progress'),
    ('DON', 'Marked') ]

TYPE_CHOICES = [
    ('Archive', 'Archive Component'),
    ('URL', 'URL Component'),
    ('Cpp', 'C/C++ Component'),
    ('PlainText', 'Plain Text Component'),
    ('Java', 'Java Component'),
]

# per-activity models, defined by instructor:

class SubmissionComponent(models.Model):
    """
    A component of the activity that will be submitted by students
    """
    activity = models.ForeignKey(Activity)
    title = models.CharField(max_length=100, help_text='Name for this component (e.g. "Part 1" or "Programming Section")')
    description = models.CharField(max_length=1000, help_text="Short explanation for this component.", null=True,blank=True)
    position = models.PositiveSmallIntegerField(help_text="The order of display for listing components.", null=True,blank=True)
    slug = AutoSlugField(populate_from='title', null=False, editable=False, unique_with='activity')

    def __cmp__(self, other):
        return cmp(self.position, other.position)
    class Meta:
        ordering = ['position']
    def __unicode__(self):
        return "%s[%s]%s"%(self.title, self.get_type(), self.description)
    def get_type(self):
        "Return xxx of xxxComponent as type"
        class_name = self.__class__.__name__
        return class_name[:class_name.index("Component")]

"""
All the subclasses follow the convention that
its name is xxxComponent where xxx will be used as type identification
"""
class URLComponent(SubmissionComponent):
    "A URL submission component"
class ArchiveComponent(SubmissionComponent):
    "An archive file (TGZ/ZIP/RAR) submission component"
    max_size = models.PositiveIntegerField(help_text="Maximum size of the archive file, in KB.", null=True, default=10000)
    extension = [".zip", ".rar", ".gzip", ".tar"]
class CppComponent(SubmissionComponent):
    "C/C++ file submission component"
    extension = [".c", ".cpp", ".cxx"]
class PlainTextComponent(SubmissionComponent):
    "Text file submission component"
    max_length = models.PositiveIntegerField(help_text="Maximum number of characters for plain text.", null=True, default=5000)
class JavaComponent(SubmissionComponent):
    "Java file submission component"
    extension = [".java"]

# list of all subclasses of SubmissionComponent:
# MUST have deepest subclasses first (i.e. nothing *after* a class is one of its subclasses)
COMPONENT_TYPES = [URLComponent, ArchiveComponent, CppComponent, PlainTextComponent, JavaComponent]

def select_all_components(activity):
    """
    Return all components for this activity as their most specific class.
    """
    components = [] # list of components
    found = set() # keep track of what has been found so we can exclude less-specific duplicates.
    for ComponentType in COMPONENT_TYPES:
        comps = list(ComponentType.objects.filter(activity=activity))
        components.extend( (c for c in comps if c.id not in found) )
        found.update( (c.id for c in comps) )

    components.sort()
    count = 1;
    for component in components:
        component.position = count*10
        count = count + 1
        component.save()
    return components



# per-submission models, created when a student/group submits an assignment:

class Submission(models.Model):
    """
    A student's or group's submission for an activity
    """
    activity = models.ForeignKey(Activity)
    created_at = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey(Member, null=True, help_text = "TA or instructor that will mark this submission")
    status = models.CharField(max_length=3, null=False,choices=STATUS_CHOICES, default = "NEW")

    "Set ownership, and make state = in progree "
    def set_owner(self, course, userid):
        member = Member.objects.filter(person__userid = userid).filter(offering = course)
        if member != []:
            self.owner = member[0]
            self.status = "INP"
            self.save()

class StudentSubmission(Submission):
    member = models.ForeignKey(Member, null=False)
    def get_userid(self):
        return self.member.person.userid
    def __unicode__(self):
        return "%s->%s@%s" % (self.member.person.userid, self.activity, self.created_at)
    
class GroupSubmission(Submission):
    group = models.ForeignKey(Group, null=False)
    submitter = models.ForeignKey(GroupMember, null = False)

    #TODO: add a item indicate who submit the assignment

    def get_userid(self):
        return self.group.manager.userid
    def __unicode__(self):
        return "%s->%s@%s" % (self.group.manager.userid, self.activity, self.created_at)

    def save(self):
        super(GroupSubmission, self).save()
        member_list = GroupMember.objects.filter(group = self.group).exclude(student = self.submitter)
        for member in member_list:
            n = NewsItem(user = member.student.person, author=submitter.student.person, course=member.courseoffering,
                source_app="group submission", title="New Group Submission", 
                content="%s has submitted new files for %s."
                    % (submitter.person,self.activity),
                url=reverse('submission.views.show_components', kwargs={'course_slug': group.courseoffering.slug, 'activity_slug': member.activity.slug})
                )
            n.save()
            

# parts of a submission, created as part of a student/group submission

class SubmittedComponent(models.Model):
    """
    Part of a student's/group's submission
    """
    submission = models.ForeignKey(StudentSubmission)
    submit_time = models.DateTimeField(auto_now_add = True)
    def get_time(self):
        "return the submit time of the component"
        return self.submit_time.strftime("%Y-%m-%d %H:%M:%S")
    def get_late_time(self):
        "return how late the submission is"
        time = self.submission.create_at - self.activity.due_date
        if time < datetime.datedelta():
            return 0
        else:
            return time
    def __cmp__(self, other):
        return cmp(other.submit_time, self.submit_time)
    class Meta:
        ordering = ['submit_time']
    def get_type(self):
        "Return xxx of Submittedxxx as type"
        class_name = self.__class__.__name__
        return class_name[9:]
    def get_size_in_kb(self):
        res = int(self.get_size())/1024
        return res
    def __unicode__(self):
        return "[%s] %s->%s@%s" % (self.get_type(), self.submission.get_userid(), self.submission.activity, self.submission.created_at)

    

class SubmittedURL(SubmittedComponent):
    component = models.ForeignKey(URLComponent, null=False)
    url = models.URLField(verify_exists=True,blank = True)
    def get_url(self):
        return self.url
    def get_size(self):
        return None
class SubmittedArchive(SubmittedComponent):
    component = models.ForeignKey(ArchiveComponent, null=False)
    archive = models.FileField(upload_to="submittedarchive", blank = True) # TODO: change to a more secure directory
    def get_url(self):
        return self.archive.url
    def get_size(self):
        return self.archive.size

class SubmittedCpp(SubmittedComponent):
    component = models.ForeignKey(CppComponent, null=False)
    cpp = models.FileField(upload_to="submittedcpp", blank = True) # TODO: change to a more secure directory
    def get_url(self):
        return self.cpp.url
    def get_size(self):
        return self.cpp.size

class SubmittedPlainText(SubmittedComponent):
    component = models.ForeignKey(PlainTextComponent, null=False)
    text = models.TextField(max_length=3000)
    def get_url(self):
        return self.text.url
    def get_size(self):
        return self.text.size

class SubmittedJava(SubmittedComponent):
    component = models.ForeignKey(JavaComponent, null=False)
    java = models.FileField(upload_to="submittedjava", blank = True) # TODO: change to a more secure directory
    def get_url(self):
        return self.java.url
    def get_size(self):
        return self.java.size


SUBMITTED_TYPES = [SubmittedURL, SubmittedArchive, SubmittedCpp, SubmittedPlainText, SubmittedJava]
def select_all_submitted_components(activity):
    submitted_component = [] # list of submitted component
    found = set() # keep track of what has been found so we can exclude less-specific duplicates.
    for SubmittedType in SUBMITTED_TYPES:
        subs = list(SubmittedType.objects.filter(submission__activity = activity))
        submitted_component.extend(s for s in subs if s.id not in found)
        found.update( (s.id for s in subs) )

    submitted_component.sort()
    return submitted_component

# TODO: group submission selector
def select_students_submitted_components(activity, userid):
    submitted_component = select_all_submitted_components(activity)
    new_submitted_component = [comp for comp in submitted_component if comp.submission.member.person.userid == userid]# [comp for comp in submitted_component if comp.submission.member.person.userid == userid]
    new_submitted_component.sort()
    return new_submitted_component

def select_students_submission_by_component(component, userid):
    submitted_component = select_students_submitted_components(component.activity ,userid)
    new_submitted_component = [comp for comp in submitted_component if comp.component == component]
    new_submitted_component.sort()
    return new_submitted_component

def filetype(file):
  """
  Do some magic to guess the filetype.
  """
  # methods extracted from the magic file (/usr/share/file/magic)
  # why not just check the filename?  Students seem to randomly rename.
  file.seek(0)
  magic = file.read(4)
  if magic=="PK\003\004" or magic=="PK00":
      return ".ZIP"
  elif magic=="Rar!":
      return ".RAR"
  elif magic[0:2]=="\037\213":
      return ".GZIP"

  file.seek(257)
  if file.read(5)=="ustar":
      return ".TAR"

  return file.name[file.name.rfind('.'):]
