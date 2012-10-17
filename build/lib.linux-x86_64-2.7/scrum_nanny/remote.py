import json
import urllib, urllib2, urlparse, cookielib
import xml.etree.ElementTree as ET
import dateutil.parser

from models import Project
from models import Sprint
from models import JiraEntries
from models import ZebraEntries
from models import JiraEntry

class Remote(object):
    def __init__(self, base_url):
        self.base_url = base_url

    def _get_request(self, url, body = None, headers = {}):
        return urllib2.Request('%s/%s' % (self.base_url, url), body, headers)

    def _request(self, url, body = None, headers = {}):
        request = self._get_request(url, body, headers)
        opener = urllib2.build_opener()
        response = opener.open(request)
        return response

    def login(self):
        pass

    def get_data(self, project):
        pass

class JiraRemote(Remote):
    def __init__(self, base_url, username, password):
        super(JiraRemote, self).__init__(base_url)

        self.username = username
        self.password = password

    def _get_request(self, url, body = None, headers = {}):
        if 'User-Agent' not in headers:
            headers['User-Agent'] = 'ScrumNanny Zebra Client';
        return super(JiraRemote, self)._get_request(url, body, headers)

    def _request(self, url, body = None, headers = {}):
        request = self._get_request(url, body, headers)
        opener = urllib2.build_opener()

        try:
            response = opener.open(request)
        except urllib2.URLError:
            raise Exception('Unable to connect to Jira. Check your connection status and try again.')

        return response

    def login(self):
        pass

    def get_data(self, project):
        url = project.get_sprint().get_jira_data('url')

        url += '&os_username=' + str(self.username)
        url += '&os_password=' + str(self.password)

        response = self._request(url)
        response_body = response.read()

        response_xml = ET.fromstring(response_body)
        stories = response_xml[0].findall('item')

        jira_entries = JiraEntries()
        for s in stories:
            story = JiraEntry()
            story.id = s.find('key').text
            story.is_nice = s.find('title').text.find('(NICE)') != -1
            story.status = int(s.find('status').get('id'))
            try:
                story.business_value = float(s.find('./customfields/customfield/[@id="customfield_10064"]/customfieldvalues/customfieldvalue').text)
            except AttributeError:
                print 'Story ' + story.id + ' has no business value defined, 0 taken as default'
            try:
                story.story_points = float(s.find('./customfields/customfield/[@id="customfield_10040"]/customfieldvalues/customfieldvalue').text)
            except AttributeError:
                print 'Story ' + story.id + ' has no story points defined, 0 taken as default'
            if story.is_over():
                try:
                    story.close_date = self.get_story_close_date(story.id)
                except AttributeError:
                    print 'Story ' + story.id + ' is discarded as it is closed, but never had the status For PO review'
                    continue
            jira_entries.append(story)
        return jira_entries

    def get_story_close_date(self, id):
        url = "/activity?maxResults=10&issues=activity+IS+issue%3Atransition&streams=issue-key+IS+"
        url += str(id)
        url += '&os_username=' + str(self.username)
        url += '&os_password=' + str(self.password)

        response = self._request(url)
        response_body = response.read()

        response_xml = ET.fromstring(response_body)
        xmlns = {"atom": "http://www.w3.org/2005/Atom"}
        close_date = response_xml.find("./atom:entry/atom:category/[@term='For PO Review']/../atom:published", namespaces=xmlns).text
        return dateutil.parser.parse(close_date)

class ZebraRemote(Remote):
    def __init__(self, base_url, username, password):
        super(ZebraRemote, self).__init__(base_url)

        self.cookiejar = cookielib.CookieJar()
        self.logged_in = False
        self.username = username
        self.password = password

    def _get_request(self, url, body = None, headers = {}):
        if 'User-Agent' not in headers:
            headers['User-Agent'] = 'ScrumNanny Zebra Client';
        return super(ZebraRemote, self)._get_request(url, body, headers)

    def _request(self, url, body = None, headers = {}):
        request = self._get_request(url, body, headers)
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.cookiejar))

        try:
            response = opener.open(request)
        except urllib2.URLError:
            raise Exception('Unable to connect to Zebra. Check your connection status and try again.')

        self.cookiejar.extract_cookies(response, request)

        return response

    def _login(self):
        if self.logged_in:
            return

        login_url = '/login/user/%s.json' % self.username
        parameters = urllib.urlencode({
            'username': self.username,
            'password': self.password,
        })

        response = self._request(login_url, parameters)
        response_body = response.read()

        if not response.info().getheader('Content-Type').startswith('application/json'):
            self.logged_in = False
            raise Exception('Unable to login')
        else:
            self.logged_in = True

    def get_data(self, project):
        report_url = 'timesheet/report/.json?option_selector='

        users = project.get_sprint().get_zebra_data('users')
        client_id = project.get_sprint().get_zebra_data('client_id')
        activities = project.get_sprint().get_zebra_data('activities')
        start_date = project.get_sprint().get_zebra_data('start_date')
        end_date = project.get_sprint().get_zebra_data('end_date')

        for user in users:
            report_url += '&users[]=' + `user`

        report_url += '&projects[]=' + `client_id`
        report_url += '&activities[]=' + str(activities)
        report_url += '&start=' + str(start_date)
        report_url += '&end=' + str(end_date)

        self._login()

        response = self._request(report_url)
        response_body = response.read()

        response_json = json.loads(response_body)
        entries = response_json['command']['reports']['report']
        print 'Will now parse %d entries found in Zebra' % len(entries)

        return self.parse_entries(entries)

    def parse_entries(self, entries):
        entries_per_date = ZebraEntries()
        for entry in entries:
            if entry['tid'] == '':
                continue
            e = self.parse_entry(entry)
            if entry['date'] in entries_per_date:
                entries_per_date[entry['date']]['entries'].append(e)
                entries_per_date[entry['date']]['total_time'] += e['time']
            else:
                o = {'entries': [e], 'total_time': e['time']}
                entries_per_date[entry['date']] = o
        return entries_per_date

    def parse_entry(self, entry):
        return {'username': str(entry['username']), 'time': float(entry['time'])}


