#!/usr/bin/env python
"""this is the model/database side of the gui in gui.py"""

import json
import random
import datetime
import os
import time

DATECODE = "%b %d, %Y"
TIMECODE = "%H:%M:%S"
DATETIMECODE = DATECODE + " " + TIMECODE

LOG_SOURCES_FILE = os.path.join("resources", "log_sources.txt")

def extractdate(date_):
    """converts the provided standard date and time
    string (ex. "Jun 28, 2017 15:18:38") to a datetime object, and then
    back to a string, but without the time portion"""
    date_ = datetime.datetime.strptime(date_, DATETIMECODE)
    return date_.strftime(DATECODE)

def seconds_since_epoch(date_):
    """returns the number of seconds since the epoch(according the the
    datetime module)"""
    epoch = datetime.datetime.fromtimestamp(0)
    return (date_ - epoch).total_seconds()

def is_valid_start_time(date_, first_date, last_date):
    """returns true if date_ falls between first_date and last_date"""
    first_time = seconds_since_epoch(first_date)
    last_time = seconds_since_epoch(last_date)
    if first_time <= seconds_since_epoch(date_) < last_time:
        return True
    return False

class Task(object):

    """This class represents a task and is able to view and manipulate
    it"s information"""

    def __init__(self, parent="root", **kwargs):
        """creates the task along with the allowed arguments, as well
        as assigns the task ID"""
        self.args = ["name",
                     "start_time",
                     "task_id",
                     "color",
                     "end_time",
                     "children",
                     "duration",
                     "graphical_id",
                     "y_pos",
                     "errors",
                     "text_graphical_id",
                     "x_pos",
                     "marker_ids",
                     "children",
                     "parent",
                     "visible",
                     "exit",
                     "exception",
                     "logdate",
                     "logfile"]
        self.information = {}
        self.hidden_information = {}

        self.hidden_information["children"] = []

        if "start_time" not in kwargs.keys():
            raise KeyError("start time must be provided at task creation")

        for key, value in kwargs.iteritems():
            if key in self.args:
                self.information[key] = value

        self.hidden_information["parent"] = parent
        self.hidden_information["visible"] = parent == "root"

        task_id = str(random.randint(1000000000, 9999999999))
        start_date = datetime.datetime.strptime(
            self.information["start_time"],
            DATETIMECODE)

        self.task_id = start_date.strftime("%M%D%Y") + task_id

        self.information["task_id"] = self.task_id
        self.hidden_information[
            "since_epoch"] = seconds_since_epoch(start_date)

    def config(self, **kwargs):
        """modifies the visible information of the task"""
        for key, value in kwargs.iteritems():
            if value is None:
                if key in self.information.keys():
                    del self.information[key]
            elif key in self.args:
                self.information[key] = value

    def hidden_config(self, **kwargs):
        """modifies the hidden information of the task"""
        for key, value in kwargs.iteritems():
            if value is None:
                if key in self.hidden_information.keys():
                    del self.hidden_information[key]
            elif key in self.args:
                self.hidden_information[key] = value

    def cget(self, arg):
        """returns the value of the argument, provided the key
        is in the task"s information dictionaries"""
        if arg in self.information:
            return self.information[arg]
        elif arg in self.hidden_information:
            return self.hidden_information[arg]

class Model(object):

    """This class holds the session data and manages the local database"""

    def __init__(self):
        self.loaded_tasks_dated = {}
        self.loaded_tasks = {}

    def get_all_children(self, task_id):
        """returns children and children of children and so on of a
        given task"""
        result = []
        for child_id in self.cget(task_id, "children"):
            result.append(child_id)
            result = result + self.get_all_children(child_id)
        return result

    def get_visible_parent(self, task_id):
        """get the first ancestor task that is visible"""
        current_id = task_id
        while self.cget(current_id, "parent") != "root":
            if self.cget(current_id, "visible"):
                break
            current_id = self.cget(current_id, "parent")
        return current_id

    def get_task_depth(self, task_id):
        """returns the number of tasks above the given task"""
        counter = 0
        current_id = task_id
        while self.cget(current_id, "parent") != "root":
            current_id = self.cget(current_id, "parent")
            counter += 1
        return counter

    def addtask(self, task):
        """adds a task to the database"""
        start_date = extractdate(task.cget("start_time"))
        task_id = task.cget("task_id")
        if start_date not in self.loaded_tasks_dated.keys():
            self.loaded_tasks_dated[start_date] = {}
        self.loaded_tasks_dated[start_date][task_id] = task
        self.loaded_tasks[task_id] = task

    def removetask(self, task_id):
        """removes a task from the database"""
        if task_id in self.loaded_tasks.keys():
            start_date = extractdate(self.cget(task_id, "start_time"))
            del self.loaded_tasks_dated[start_date][task_id]
            del self.loaded_tasks[task_id]

    def getdatetasks(self, date_):
        """returns a list of task ID"s for all tasks whose start
        time was on the provided day"""
        if not date_.strftime(DATECODE) in self.loaded_tasks_dated.keys():
            self.update(date_)
        return [task_id for task_id in self.loaded_tasks_dated[
            date_.strftime(DATECODE)].keys()]

    def config(self, task_id, **kwargs):
        """returns the result of config of the provided task.
        look at Task for more details"""
        if task_id in self.loaded_tasks.keys():
            if "start_time" in kwargs.keys():
                new_task = Task(start_time=kwargs["start_time"])
                for key, value in self.getinfo(task_id).iteritems():
                    new_task.information[key] = value
                for key, value in self.gethiddeninfo(task_id).iteritems():
                    new_task.hidden_information[key] = value
                new_task.config(**kwargs)
                self.removetask(task_id)
                self.addtask(new_task)
            start_date = extractdate(self.cget(task_id, "start_time"))
            self.loaded_tasks[task_id].config(**kwargs)
            self.loaded_tasks_dated[start_date][task_id].config(**kwargs)

    def hidden_config(self, task_id, **kwargs):
        """returns the result of hidden_config of the provided task.
        look at Task for more details"""
        if task_id in self.loaded_tasks.keys():
            start_date = extractdate(self.cget(task_id, "start_time"))
            self.loaded_tasks[task_id].hidden_config(**kwargs)
            self.loaded_tasks_dated[start_date][
                task_id].hidden_config(**kwargs)

    def cget(self, task_id, arg):
        """returns the result of cget of the provided task. look at
        Task for more details"""
        if task_id in self.loaded_tasks.keys():
            return self.loaded_tasks[task_id].cget(arg)

    def dateexists(self, date_):
        """returns true if the date provided is in the database"""
        date_ = date_.strftime(DATECODE)
        if date_ in self.loaded_tasks_dated.keys():
            return True
        return False

    def getinfo(self, task_id):
        """returns the entire information_sdictionary of a task"""
        if task_id in self.loaded_tasks.keys():
            return self.loaded_tasks[task_id].information

    def gethiddeninfo(self, task_id):
        """returns the entire hidden_information dictionary of a task"""
        if task_id in self.loaded_tasks.keys():
            return self.loaded_tasks[task_id].hidden_information

    def update(self, date_):
        """reads a json file and creates all the tasks associated"""

        if not date_.strftime(DATECODE) in self.loaded_tasks_dated.keys():
            self.loaded_tasks_dated[date_.strftime(DATECODE)] = {}

        filepath = os.path.join(
            "local_database",
            date_.strftime("%b_%d_%Y.json"))
        if not os.path.isfile(filepath):
            with open(filepath, "w") as jsonfile:
                json.dump({}, jsonfile)
        with open(filepath) as jsonfile:
            newtasks = json.load(jsonfile)
            for task in newtasks.values():
                if "parent" not in task[0].keys():
                    parent = "root"
                else:
                    parent = task[0]["parent"]
                obj = Task(parent, start_time=task[0]["start_time"])
                task_id = obj.cget("task_id")
                for key, value in task[0].iteritems():
                    try:
                        key = key.encode("utf-8")
                        value = value.encode("utf-8")
                    except AttributeError:
                        pass
                    obj.information[key] = value
                for key, value in task[1].iteritems():
                    try:
                        key = key.encode("utf-8")
                        value = value.encode("utf-8")
                    except AttributeError:
                        pass
                    obj.hidden_information[key] = value
                self.addtask(obj)
                if self.cget(task_id, "parent") == "root":
                    self.hidden_config(task_id, visible=True)
                else:
                    self.hidden_config(task_id, visible=False)

    def save_database(self):
        """saves all tasks to json files"""
        for date_ in self.loaded_tasks_dated.keys():
            content = {}
            for task_id in self.loaded_tasks_dated[date_].keys():
                content[task_id] = [
                    self.getinfo(task_id),
                    self.gethiddeninfo(task_id)]
            filepath = os.path.join("local_database",
                                    date_.replace(",",
                                                  "").replace(" ",
                                                              "_") + ".json")
            with open(filepath, "w") as jsonfile:
                json.dump(content, jsonfile, indent=4, sort_keys=True)

    def search(self, search_term, search_text, tasks_to_search):
        """searches through the given task IDs for the details provided"""
        search_term = search_term.replace(" ", "_")
        results = {}

        tasks_to_search = [str(task_id) for task_id in tasks_to_search]

        if search_term == "task_id":
            if search_text in tasks_to_search:
                results[search_text] = self.cget(search_text, "name")
            else:
                for task_id in tasks_to_search:
                    if search_text in task_id:
                        results[task_id] = self.cget(task_id, "name")
        else:
            for task_id in tasks_to_search:
                if search_text in str(self.cget(task_id, search_term)):
                    results[task_id] = self.cget(task_id, search_term)

        return results

    def clean_period(self, first_date, last_date):
        """removes all tasks whose start time falls between first_date
        and last_date"""
        task_ids = []
        for i in range((last_date - first_date).days + 1):
            task_ids += self.getdatetasks(first_date +
                                          datetime.timedelta(days=i))
        for task_id in task_ids:
            if is_valid_start_time(datetime.datetime.strptime(
                    self.cget(task_id, "start_time"),
                    DATETIMECODE),
                                   first_date, last_date):
                self.removetask(task_id)

    def load_task(self, task_dict, parent_task):
        """creates a new task based on information from self.parseupdate"""
        date = datetime.datetime.fromtimestamp(task_dict["start"])
        parent_id = parent_task if parent_task == "root" else parent_task.cget(
            "task_id")
        task = Task(parent_id, start_time=date.strftime(DATETIMECODE))
        task.config(name=task_dict["name"])
        if "finish" in task_dict.keys():
            end_date = datetime.datetime.fromtimestamp(
                task_dict["finish"]).strftime(DATETIMECODE)
            task.config(end_time=end_date)
        else:
            task.config(end_time="In Progress")
        if "exit" in task_dict.keys():
            task.config(exit=task_dict["exit"])
        if "except" in task_dict.keys():
            task.config(exception=task_dict["except"])
        if "logdate" in task_dict.keys():
            logdate = datetime.datetime.fromtimestamp(
                task_dict["logdate"]).strftime(DATETIMECODE)
            task.hidden_config(logdate=logdate)
            task.config(logfile=task_dict["logfile"])

        if parent_task != "root":
            parent_task.hidden_information[
                "children"].append(task.cget("task_id"))
        for child in task_dict["subjobs"]:
            self.load_task(child, task)

        self.addtask(task)

    def parseupdate(self, first_date, last_date):
        """parses through log files for new tasks"""
        with open(LOG_SOURCES_FILE, "r") as txtfile:
            target_logs = [line.strip() for line in txtfile.readlines()]
        self.clean_period(first_date, last_date)
        for logfile_path in target_logs:
            for i in range(0, (last_date - first_date).days + 1):
                date_to_check = first_date + datetime.timedelta(days=i)
                os.system("triglog.py --date={} {}".format(
                    seconds_since_epoch(date_to_check),
                    logfile_path))
                log_out_file = os.path.join("resources", "logs.json")
                with open(log_out_file, "r") as jsonfile:
                    log = json.load(jsonfile)
                    for task in log["root"]["subjobs"]:
                        date = datetime.datetime.fromtimestamp(task["start"])
                        if is_valid_start_time(date, first_date, last_date):
                            self.load_task(task, "root")
