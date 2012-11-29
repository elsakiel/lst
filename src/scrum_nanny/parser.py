import yaml
from models import Project
from models import Sprint

class SecretParser:
    def __init__(self, url):
        data_file = open(url)
        settings = yaml.load(data_file)
        data_file.close()

        self.zebra_data = settings['zebra']
        self.jira_data = settings['jira']

    def get_zebra(self, key):
        return self.zebra_data[key]

    def get_jira(self, key):
        return self.jira_data[key]

class ConfigParser:
    def __init__(self, user_project, user_index):
        self.u_project = user_project
        self.u_index = user_index

    def load_config(self, url):
        data_file = open(url)
        settings = yaml.load(data_file)
        data_file.close()
        return settings

    def parse(self, data):
        # check if the project specified exists
        for proj in data['projects']:
            p = proj['project']
            if p['name'] == self.u_project:
                project = Project()
                project.set_name(unicode(p['name']))
                projectData = p
                break
        try:
            print "Project %s found in config" % (project.get_name())
        except:
            print "Project %s not found. Make sure it's defined in your settings file" % (self.u_project)
            return

        # if a sprint index is specified check that it exists
        if self.u_index is not None:
            try:
                projectData['sprints']
            except:
                print "There is no sprint defined in your config for the project %s" % (project.get_name())
                return

            found = 0
            for spr in projectData['sprints']:
                s = spr['sprint']
                if unicode(s['index']) == self.u_index:
                    found = 1
                    break
            if found == 0:
                print "There is no sprint with the index %s defined in your config for the project %s" % (self.u_index, project.get_name())
                return
        else:
            print "No sprint index specified, taking last defined per default"
            spr = projectData['sprints'][len(projectData['sprints']) - 1]
            s = spr['sprint']

        try:
            sprint = Sprint()
            sprint.set_index(unicode(s['index']))
            sprint.set_jira_data(s['jira'])
            sprint.set_zebra_data(s['zebra'])
            sprint.commited_man_days = unicode(s['commited_man_days'])
            project.set_sprint(sprint)
            print "Sprint %s found in config" % (sprint.get_index())
        except:
            print "Either the sprint you specified was not found or there was no sprint defined in your config"
            return

        return project

