"""
davislib.models

This module contains important objects.
"""
import requests
import re
import datetime
from bs4 import BeautifulSoup, element
from enum import Enum

"""
Data containers
"""
class Term(object):
    """
    Container for term information
    """
    class Session(Enum):
        """
        Enum representation of all annual Term sessions
        """
        FALL_QUARTER = '10'
        FALL_SEMESTER = '09'
        SUMMER_SESSION_2 = '07'
        SUMMER_SPECIAL = '06'
        SUMMER_SESSION_1 = '05'
        SPRING_QUARTER = '03'
        SPRING_SEMESTER = '02'
        WINTER_QUARTER = '01'

        @classmethod
        def values(cls):
            """
            Returns list of values ('10', '09') 
            """
            return [m.value for m in cls.__members__.values()]

        def __str__(self):
            return self._name_.replace('_', ' ').title()

    def __init__(self, year, session):
        """
        Parameters:
            year: 
                e.g. 2014
            session: Session enumerated constant
                e.g. Term.Session.FALL_QUARTER
        """
        self.session = self.Session(session)
        self.year = year

    @property
    def code(self):
        """
        Returns term code, used by 
        """
        return '{0}{1}'.format(self.year, self.session.value)
    
    def __str__(self):
        return '{0} {1}'.format(self.session, self.year)

    def __repr__(self):
        return '<Term {}>'.format(self.code)

    def __eq__(self, other):
        return str(self.year) == str(other.year) and self.session == other.session

class Course(object):
    """
    Container for course information
    Attributes:

    """
    _attrs = ['name', 
            'number',
            'section',
            'title',
            'units',
            'instructor',
            'subject',
            'ge_credit',
            'available_seats',
            'max_enrollment',
            'meetings',
            'description',
            'final_exam',
            'drop_time']

    def __init__(self, crn, term, **attrs):
        """
        Parameters:
            crn: five-digit course reference number
            term: Term object
            attrs: Attributes prepared in Registrar
        """
        #: Course reference number
        #: e.g. 74382
        self.crn = crn

        #: Course term object
        #: e.g. <Term 201410>
        self.term = term

        #: Course name string 
        #: e.g. 'ECS 040'
        self.name = attrs['name']
        
        #: Course number
        #: e.g. '040'
        self.number = attrs['number']
        
        #: Section code string 
        #: e.g. 'A01'
        self.section = attrs['section']

        #: Course title string 
        #: e.g. 'Intro to Programming'
        self.title = attrs['title']

        #: Number of units, scalar float or tuple (low, hi) 
        #: e.g. 2.5 or (1.0,5.0)
        self.units = attrs['units']

        #: Instructor name string
        #: e.g. 'Sean Davis'
        self.instructor = attrs['instructor']

        #: Subject name string
        #: e.g. 'Engineering Computer Science'
        self.subject = attrs['subject']

        #: List of GE credit satisfied
        #: e.g. ['Arts & Humanities', 'Oral Literacy']
        self.ge_credit = attrs['ge_credit']

        #: Number of available seats
        #: e.g. 30
        self.available_seats = attrs['available_seats']

        #: Maximum enrollment number
        #: e.g. 99
        self.max_enrollment = attrs['max_enrollment']

        #: Meetings, as list of meetings represented as dictionaries
        #: e.g. [
        #:        {'days': 'TR', 'hours': '10:30 - 11:50 AM', 'location': 'Storer Hall 1322'}]
        #:        ...
        #:      ]
        self.meetings = attrs['meetings']

        #: Course description string
        self.description = attrs['description']

        #: Final exam time, as datetime.datetime object 
        #: or string 'See Instructor'
        self.final_exam = attrs['final_exam']

        #: Drop time string
        #: e.g. '20 Day Drop'
        self.drop_time = attrs['drop_time']

    def __str__(self):
        return '{} - {} - {}'.format(self.term, self.course_name, self.course_title)

    def __repr__(self):
        return '<Course {} ({})>'.format(self.crn, repr(self.term))

    def __eq__(self, other):
        return self.crn == other.crn and self.term == other.term

"""
Applications
"""

class InvalidLoginError(Exception):
    pass

class Application(object):
    """
    Base class for UC Davis web app
    """
    USER_AGENT=('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537'
                '.36 (KHTML, like Gecko) Chrome/40.0.2214.115 Safari/537.36')

    def __init__(self, shared_app=None):
        """
        Parameters:
            (optional) shared_app: object deriving from Application 
                                   whose session will be used in new object
                                   (Specify this parameter if you wish to share cookies)
        """
        super(Application, self).__init__()

        if shared_app:
            if isinstance(shared_app, __class__):
                self.s = shared_app.s
            else:
                raise ValueError("shared_app does not derive from Application")
        else:
            self.s = requests.Session()
            self.s.headers.update({'User-Agent': self.USER_AGENT})

    def request(self, method, base, endpoint, **kwargs):
        return self.s.request(method, ''.join([base, endpoint]), **kwargs)

    def get(self, *args, **kwargs):
        """
        Executes GET request on application BASE at endpoint
        Parameters:
            see Application.request
        """
        return self.request('get', self.__class__.BASE, *args, **kwargs)

    def post(self, *args, **kwargs):
        """
        Executes POST request on application BASE at endpoint
        Parameters:
            see Application.request
        """
        return self.request('post', self.__class__.BASE, *args, **kwargs)

class ProtectedApplication(Application):
    """
    Base class for UC Davis web app relying on CAS (central authentication service)
    """         
    def __init__(self, username=None, password=None, shared_app=None):
        """
        Parameters:
            username: kerberos login id
            password: kerberos password
            (optional) shared_app: object deriving from Application
                                   whose session will be shared with self.
                                   if derives from ProtectedApplication,
                                   then username and password will be copied as well 
                                   for re-authentication.

        """
        super(__class__, self).__init__(shared_app=shared_app)

        # Initialize CAS class with self as shared_app
        # this will share authentication cookies
        if isinstance(shared_app, __class__):
            self.auth_service = self.CAS(shared_app.username, 
                                         shared_app.password, 
                                         shared_app=self)
        if username and password: 
            self.auth_service = self.CAS(username, 
                                         password, shared_app=self)

    def request(self, method, base, endpoint, **kwargs):
        """
        See Application for main functionality
        Ensures user is authenticated before returning response
        Parameters:
            See Application.get
        """
        r = super(__class__, self).request(method, base, endpoint, **kwargs)

        if 'cas.ucdavis' not in r.url:
            # already authed
            return r
        else:
            # re-auth then send request again
            self.auth_service.auth()
            return super(__class__, self).request(method, base, endpoint, **kwargs)

    class CAS(Application):
        BASE='https://cas.ucdavis.edu'
        LOGIN_ENDPOINT='/cas/login'
        def __init__(self, username, password, shared_app):
            super(__class__, self).__init__(shared_app=shared_app)

            self.username = username
            self.password = password

        def auth(self):
            auth_page = self.get(self.LOGIN_ENDPOINT)
            if '<div id="msg" class="success"' in auth_page.text:
                return # already logged in

            soup = BeautifulSoup(auth_page.text)
            login_form = soup.find("form", id="fm1")

            data = dict()
            # Make sure to submit hidden fields
            for child in login_form.find_all(text=False):
                if child.has_attr('name') and child.has_attr('value'):
                    data[child['name']] = child['value']

            data['username'] = self.username
            data['password'] = self.password

            r = self.post(login_form['action'], data=data)
            if '<div id="msg" class="success"' not in r.text:
                raise InvalidLoginError()