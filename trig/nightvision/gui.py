#!/usr/bin/env python
"""this is the view and controller part of this gui, which visualizes nightly processes"""

# pylint: disable=too-many-instance-attributes
# pylint: disable=unused-argument

import Tkinter as tk
import tkMessageBox
import tkFileDialog
import collections
import datetime
import json
import os
import sys
import model

# ==================================================
# ==================== SETUP =======================
# ==================================================

VERSION = "1.0.0"

# -- Constants --

PALETTE_FILE = os.path.join("resources", "palette.txt")
WINDOW_INFORMATION_FILE = os.path.join("resources", "window_information.json")
HELPSTR_FILE = os.path.join("resources", "helpstr.txt")
LOG_SOURCES_FILE = os.path.join("resources", "log_sources.txt")

with open(WINDOW_INFORMATION_FILE) as jfile:
    win_info = json.load(jfile)  # pylint: disable=invalid-name
    WINDOW_SIZE = win_info["size"]
with open(HELPSTR_FILE) as f:
    HELPSTR = f.read()
VIEW_FRAME_WIDTH = WINDOW_SIZE[0] - 280
FONT = ("Courier New", 11)
TASK_FONT = (FONT[0], 12 if WINDOW_SIZE[1] >= 1200 else 11)
FONT_BOLD = ("Courier New", 11, "bold")
BIG_FONT = ("Courier New", 24)
TASK_WIDTH = 15 + (5 if WINDOW_SIZE[1] >= 1200 else 0)
DATECODE = "%b %d, %Y"
TIMECODE = "%H:%M:%S"
DATETIMECODE = "%b %d, %Y %H:%M:%S"

DETAILS_BG_COLOR = "#d9d9d9"  # default is #d9d9d9

NO_END_TIME_INDICATORS = ["In Progress", None]

# -- Functions --

def print3(*args):
    """
    Python 2 & 3 compatible print function.
    """
    string = " ".join([str(x) for x in args])
    sys.stdout.write(string + "\n")
    sys.stdout.flush()

def today():
    """returns the current, updated time"""
    return datetime.datetime.now()

def extractdate(date_):
    """converts the provided standard date and time
    string (ex. "Jun 28, 2017 15:18:38") to a datetime object, and then back to a string, but
    without the time portion"""
    date_ = datetime.datetime.strptime(date_, DATETIMECODE)
    return date_.strftime(DATECODE)

def displacedate(date_, days):
    """displace datetime object by the given days"""
    if days < 0:
        return date_ - datetime.timedelta(days=abs(days))
    else:
        return date_ + datetime.timedelta(days=days)

def secs_since_midnight(date_):
    """returns the number of seconds since midnight of the day given"""
    day = date_.replace(hour=0, minute=0, second=0, microsecond=0)
    return (date_ - day).total_seconds()

def duration_to_hms(duration):
    """converts number of seconds to the H:M:S format"""
    duration = int(duration)
    minutes, seconds = divmod(duration, 60)
    hours, minutes = divmod(minutes, 60)
    return "%d:%02d:%02d" % (hours, minutes, seconds)

def definecolors():
    """defines the possible colors to draw the tasks"""
    with open(PALETTE_FILE) as txtfile:
        colors = collections.OrderedDict()
        for line in txtfile.readlines():
            color = line.strip().split()

            if (int(color[1]) * 0.299 + int(color[2])
                    * 0.587 + int(color[3]) * 0.114) > 170:
                key = "#" + color[0]
                colors[key] = "black"
            elif (int(color[1]) * 0.299 + int(color[2]) * 0.587 + int(color[3]) * 0.114) <= 169:
                key = "#" + color[0]
                colors[key] = "white"
    return colors

def time_displace_24h_view(view_date, task_id):
    """displaces the task time so the task is displayed on the right day
    (for the 24h view)"""
    start_date = extractdate(DATABASE.cget(task_id, "start_time"))
    if DATABASE.cget(task_id, "end_time") in NO_END_TIME_INDICATORS:
        if since_epoch(today()) > since_epoch(
                view_date.replace(hour=11, minute=59, second=59)):
            end_date = view_date.strftime(DATECODE)
            end_secs = 43199
        else:
            end_date = today().strftime(DATECODE)
            end_secs = secs_since_midnight(today())
    else:
        end_date = extractdate(DATABASE.cget(task_id, "end_time"))
        end_secs = secs_since_midnight(datetime.datetime.strptime(DATABASE.cget(task_id,
                                                                                "end_time"),
                                                                  DATETIMECODE))
    start_secs = secs_since_midnight(datetime.datetime.strptime(DATABASE.cget(task_id,
                                                                              "start_time"),
                                                                DATETIMECODE))
    start_is_day_before = start_date == displacedate(
        view_date, -1).strftime(DATECODE)
    if start_is_day_before and (end_secs >= 43200
                                or (end_date == view_date.strftime(DATECODE)
                                    and end_secs < 43200)):
        start_secs -= 43200
        if end_date == view_date.strftime(DATECODE):
            end_secs += 43200
        else:
            end_secs -= 43200
        accepted = True
    elif start_date == displacedate(view_date, 0).strftime(DATECODE) and start_secs < 43200:
        start_secs += 43200
        end_secs += 43200
        accepted = True
    else:
        accepted = False
        start_secs = 0
        end_secs = 0

    return accepted, start_secs, end_secs

def since_epoch(date_):
    """returns the number of seconds since the epoch(according the the datetime module)"""
    epoch = datetime.datetime.fromtimestamp(0)
    return (date_ - epoch).total_seconds()

def time_displace_48h_view(view_date, task_id):
    """displaces the time of the given task so that it is displayed on the right day
    (for the 48h view)"""
    start_date = extractdate(DATABASE.cget(task_id, "start_time"))
    if DATABASE.cget(task_id, "end_time") in NO_END_TIME_INDICATORS:
        if since_epoch(today()) > since_epoch(
                view_date.replace(hour=11, minute=59, second=59)):
            end_date = view_date.strftime(DATECODE)
            end_secs = 43199
        else:
            end_date = today().strftime(DATECODE)
            end_secs = secs_since_midnight(today())
    else:
        end_date = extractdate(DATABASE.cget(task_id, "end_time"))
        end_secs = secs_since_midnight(datetime.datetime.strptime(DATABASE.cget(task_id,
                                                                                "end_time"),
                                                                  DATETIMECODE))
    start_secs = secs_since_midnight(datetime.datetime.strptime(DATABASE.cget(task_id,
                                                                              "start_time"),
                                                                DATETIMECODE))
    start_is_two_days_before = start_date == displacedate(
        view_date, -2).strftime(DATECODE)
    end_is_not_two_days_before = bool(end_date == displacedate(
        view_date, -1).strftime(DATECODE) or end_date == view_date.strftime(DATECODE))
    if start_is_two_days_before and (
            end_secs >= 43200 or end_is_not_two_days_before):
        start_secs -= 43200
        if end_date == view_date.strftime(DATECODE) and end_secs < 43200:
            end_secs += 129600
        elif end_date == displacedate(
                view_date, -1).strftime(DATECODE):
            end_secs += 43200
        else:
            end_secs -= 43200
        accepted = True
    elif start_date == displacedate(view_date, 0).strftime(DATECODE) and start_secs < 43200:
        start_secs += 129600
        end_secs += 129600
        accepted = True
    elif start_date == displacedate(view_date, -1).strftime(DATECODE):
        start_secs += 43200
        if end_date == view_date.strftime(
                DATECODE):
            end_secs += 129600
        else:
            end_secs += 43200
        accepted = True
    else:
        accepted = False
        start_secs = 0
        end_secs = 0
    return accepted, start_secs, end_secs

def on_resize(event):
    """adjusts to resizing of the window"""
    with open(WINDOW_INFORMATION_FILE, "w") as jsonfile:
        new_height = event.height - 2
        info = {
            "size": (
                event.width +
                295,
                620 if new_height < 620 else new_height)}
        json.dump(info, jsonfile, indent=4, sort_keys=True)
    VIEW.open_resize_window()

# =======================================================
# ==================== CONTROLLER =======================
# =======================================================

class Controller(object):

    """this class manages the View class and the information it displays"""

    def __init__(self):
        self.current_day = today()
        self.tasks_showing = []
        self.tasks_loaded = []
        self.info_content = ""
        self.current_mode = "24h"
        self.search_by_term = "name"
        self.normal_search_options = [
            "name",
            "task_id",
            "start_time",
            "end_time",
            "duration",
            "exit",
            "logfile"]
        self.search_options = self.normal_search_options
        self.search_option_active = False
        self.search_box_first_click = True
        self.tooltips = []
        self.tooltip_enabled = True
        self.debug_mode = False
        self.last_canvas_click = datetime.datetime.now()

    def display_info(self, event, task_id):
        """displays details about what is being viewed on the right information panel"""

        self.last_canvas_click = datetime.datetime.now().replace(microsecond=0)

        task_info_content = ""
        for key in self.normal_search_options:
            task_info_content += str(key).replace("_", " ") + ": " + \
                str(DATABASE.cget(task_id, key)) + "\n"
        if len(self.normal_search_options) < len(
                DATABASE.getinfo(task_id).keys()):
            for key, value in DATABASE.getinfo(task_id).iteritems():
                key = str(key).encode("utf-8")
                value = str(value).encode("utf-8")
                if key not in self.normal_search_options:
                    task_info_content += key.replace("_", " ") + ": " + value
        if DATABASE.cget(task_id, "errors") is not None:
            task_info_content += "\nERRORS:\n"
            for error_info in DATABASE.cget(task_id, "errors"):
                task_info_content += "====== {} ======\n{}\n".format(
                    error_info[0],
                    error_info[1])

        hidden_content = "DEBUG INFO:\n"
        for key, value in DATABASE.gethiddeninfo(task_id).iteritems():
            if key == "errors":
                continue
            key = str(key).encode("utf-8")
            value = str(value).encode("utf-8")
            hidden_content += key.replace("_", " ") + ": " + value + "\n"

        VIEW.select_task(task_id, False)
        VIEW.info_insert(task_info_content, hidden_content)

    def canvas_click(self, event):
        """if the canvas background was clicked, it will deselect all tasks"""
        if not datetime.datetime.now().replace(
                microsecond=0) == self.last_canvas_click:
            VIEW.info_main_view_mode()

    def parseupdate(self):
        """initiates the reading of log files"""
        if self.current_mode == "24h":
            first_date = (self.current_day - datetime.timedelta(days=1)).replace(hour=18,
                                                                                 minute=0,
                                                                                 second=0)
        elif self.current_mode == "48h":
            first_date = (self.current_day - datetime.timedelta(days=2)).replace(hour=18,
                                                                                 minute=0,
                                                                                 second=0)
        last_date = self.current_day.replace(hour=18, minute=0, second=0)
        DATABASE.parseupdate(first_date, last_date)
        self.chart_draw(self.current_day)
        # Necessary for durations of new tasks to be calculated:
        self.chart_draw(self.current_day)

    def disable_tooltips(self):
        """disables the information windows when hovering over a task"""
        for tooltip in self.tooltips:
            tooltip.destroy()
        self.tooltips = []
        self.tooltip_enabled = False

    def enable_tooltips(self, event):
        """re-enables the information windows when hovering over a task"""
        self.tooltip_enabled = True

    def search(self, event):
        """searches and displays tasks whose names contain the searched text"""
        results = DATABASE.search(
            self.search_by_term,
            VIEW.search_entry.get(),
            self.tasks_loaded)

        if len(results.keys()) > 1 or len(results.keys()) == 0:
            new_info = "Search results: " + str(len(results.keys())) + "\n\n"
            for task_id in results.keys():
                if self.search_by_term == "task_id":
                    new_info += "{} - Name: {} \n\n".format(
                        task_id,
                        results[task_id])
                else:
                    new_info += "{} - ID: {}\n\n".format(
                        results[task_id],
                        task_id)
            VIEW.info_insert(new_info)
        else:
            task_id = results.keys()[0]
            self.display_info("", task_id)
            if DATABASE.cget(task_id, "visible"):
                VIEW.select_task(task_id)
            else:
                VIEW.select_task(DATABASE.get_visible_parent(task_id))

    def show_children(self, event, task_id, set_to=None):
        """toggles the visibility status of all children of a given task"""
        self.disable_tooltips()
        if set_to is not None:
            DATABASE.hidden_config(task_id, visible=set_to)
        for child_id in DATABASE.cget(task_id, "children"):
            if DATABASE.cget(child_id, "visible"):
                visibility = False
                for grandchild_id in DATABASE.cget(child_id, "children"):
                    self.show_children("", grandchild_id, visibility)
            else:
                visibility = True
            if set_to is not None:
                visibility = set_to
            DATABASE.hidden_config(child_id, visible=visibility)
        self.chart_draw(self.current_day)

    def chart_draw(self, date_, override=True):
        """calls either self.chart_draw_24h or self.chart_draw_48h based
        on the current mode"""
        if self.current_mode == "24h" or self.current_mode is None:
            self.chart_draw_24h(date_, override)
        elif self.current_mode == "48h":
            self.chart_draw_48h(date_, override)

    def attempt_draw_24h(self, task_id):
        """in 24h mode: if the task provided is qualified to be displayed, it is displayed"""

        DATABASE.hidden_config(
            task_id,
            color=COLORS.keys()[
                DATABASE.get_task_depth(task_id)])

        accepted, start_secs, end_secs = time_displace_24h_view(
            CONTROLLER.current_day, task_id)
        duration = abs(int(end_secs - start_secs))
        if accepted:
            self.tasks_loaded.append(task_id)
            if not DATABASE.cget(task_id, "visible"):
                for child_id in DATABASE.cget(task_id, "children"):
                    self.attempt_draw_24h(child_id)
                return
            self.tasks_showing.append(task_id)
            x_pos = (start_secs / 86400.0) * \
                (VIEW_FRAME_WIDTH - 58) - 2  # Here I account for inaccuracy,
            # whose source I cannot identify
            width = ((end_secs - start_secs) / 86400.0) * \
                (VIEW_FRAME_WIDTH - 58) + 2  # Same here
            y_pos = len(self.tasks_showing) * (TASK_WIDTH + 5)
            obj, textobj = VIEW.draw_task(task_id, x_pos, width, y_pos)
            DATABASE.hidden_config(
                task_id,
                graphical_id=obj,
                text_graphical_id=textobj)
            DATABASE.hidden_config(
                task_id,
                y_pos=y_pos,
                x_pos=int(x_pos))
            TaskTooltip(task_id)
            VIEW.timechart_canvas.tag_bind(obj, "<1>",
                                           lambda a="", b=task_id: self.display_info(a, b))
            VIEW.timechart_canvas.tag_bind(obj, "<Double-Button-1>",
                                           lambda a="", b=task_id: self.show_children(a, b))
            VIEW.timechart_canvas.tag_bind(textobj, "<1>",
                                           lambda a="", b=task_id: self.display_info(a, b))
            VIEW.timechart_canvas.tag_bind(textobj, "<Double-Button-1>",
                                           lambda a="", b=task_id: self.show_children(a, b))
            for marker_id in DATABASE.cget(task_id, "marker_ids"):
                VIEW.timechart_canvas.tag_bind(marker_id, "<1>",
                                               lambda a="", b=task_id: self.display_info(a, b))
                VIEW.timechart_canvas.tag_bind(marker_id, "<Double-Button-1>",
                                               lambda a="", b=task_id: self.show_children(a, b))
            if DATABASE.cget(task_id, "end_time") in NO_END_TIME_INDICATORS:
                disp_duration = "In Progress"
            else:
                disp_duration = duration_to_hms(duration)

            self.info_content += "{} - duration: {}\n".format(DATABASE.cget(task_id, "name"),
                                                              disp_duration)
            DATABASE.config(task_id, duration=disp_duration)

        for child_id in DATABASE.cget(task_id, "children"):
            self.attempt_draw_24h(child_id)

    def attempt_draw_48h(self, task_id):
        """in 48h mode: if the task provided is qualified to be displayed, it is displayed"""

        DATABASE.hidden_config(
            task_id,
            color=COLORS.keys()[
                DATABASE.get_task_depth(task_id)])

        accepted, start_secs, end_secs = time_displace_48h_view(
            CONTROLLER.current_day, task_id)
        duration = abs(int(end_secs - start_secs))
        if accepted:
            self.tasks_loaded.append(task_id)
            if not DATABASE.cget(task_id, "visible"):
                for child_id in DATABASE.cget(task_id, "children"):
                    self.attempt_draw_24h(child_id)
                return
            self.tasks_showing.append(task_id)
            x_pos = (start_secs / 172800.0) * \
                (VIEW_FRAME_WIDTH - 56) - 4  # Here I account for inaccuracy,
            # whose source I cannot identify
            width = ((end_secs - start_secs) / 172800.0) * \
                (VIEW_FRAME_WIDTH - 56)  # Same here
            y_pos = len(self.tasks_showing) * (TASK_WIDTH + 5)
            obj, textobj = VIEW.draw_task(task_id, x_pos, width, y_pos)
            DATABASE.hidden_config(
                task_id,
                graphical_id=obj,
                text_graphical_id=textobj)
            DATABASE.hidden_config(
                task_id,
                y_pos=y_pos,
                x_pos=int(x_pos))
            TaskTooltip(task_id)
            VIEW.timechart_canvas.tag_bind(obj, "<1>",
                                           lambda a="", b=task_id: self.display_info(a, b))
            VIEW.timechart_canvas.tag_bind(obj, "<Double-Button-1>",
                                           lambda a="", b=task_id: self.show_children(a, b))
            VIEW.timechart_canvas.tag_bind(textobj, "<1>",
                                           lambda a="", b=task_id: self.display_info(a, b))
            VIEW.timechart_canvas.tag_bind(textobj, "<Double-Button-1>",
                                           lambda a="", b=task_id: self.show_children(a, b))
            for marker_id in DATABASE.cget(task_id, "marker_ids"):
                VIEW.timechart_canvas.tag_bind(marker_id, "<1>",
                                               lambda a="", b=task_id: self.display_info(a, b))
                VIEW.timechart_canvas.tag_bind(marker_id, "<Double-Button-1>",
                                               lambda a="", b=task_id: self.show_children(a, b))
            if DATABASE.cget(task_id, "end_time") in NO_END_TIME_INDICATORS:
                disp_duration = "In Progress"
            else:
                disp_duration = duration_to_hms(duration)

            self.info_content += "{} - duration: {}\n".format(DATABASE.cget(task_id, "name"),
                                                              disp_duration)
            DATABASE.config(task_id, duration=disp_duration)

        for child_id in DATABASE.cget(task_id, "children"):
            self.attempt_draw_48h(child_id)

    def chart_draw_24h(self, view_date=today(), override=True):
        """draws graph of tasks over 24 hours"""
        if self.current_mode == "24h" and not override:
            return

        if not DATABASE.dateexists(view_date):
            DATABASE.update(view_date)
        if not DATABASE.dateexists(displacedate(view_date, -1)):
            DATABASE.update(displacedate(view_date, -1))

        VIEW.timechart_reset("24h", view_date)
        VIEW.draw_x_labels_24h_view()
        tasks_available = DATABASE.getdatetasks(displacedate(view_date, -1)) +\
            DATABASE.getdatetasks(view_date)
        VIEW.draw_lines_and_labels(displacedate(view_date, -1).strftime(DATECODE) + " - " +
                                   view_date.strftime(DATECODE), len(tasks_available))
        self.info_content = ""
        self.tasks_showing = []
        self.tasks_loaded = []

        tasks_to_show = {}
        for task_id in tasks_available:
            tasks_to_show[task_id] = DATABASE.cget(task_id, "since_epoch")

        for tooltip in self.tooltips:
            tooltip.destroy()

        self.tooltips = []

        for task_info in sorted(tasks_to_show.iteritems(), key=lambda t: t[1]):
            task_id = task_info[0]

            if DATABASE.cget(task_id, "parent") == "root":
                self.attempt_draw_24h(task_id)

        DATABASE.save_database()
        VIEW.timechart_canvas.config(scrollregion=(0, 0, 0,
                                                   len(self.tasks_showing) *
                                                   (TASK_WIDTH + 5) + 200))
        VIEW.display_main_details(self.info_content)

    def chart_draw_48h(self, view_date=today(), override=True):
        """draws graph of tasks over 48 hours"""

        if self.current_mode == "48h" and not override:
            return

        if not DATABASE.dateexists(view_date):
            DATABASE.update(view_date)
        if not DATABASE.dateexists(displacedate(view_date, -1)):
            DATABASE.update(displacedate(view_date, -1))
        if not DATABASE.dateexists(displacedate(view_date, -2)):
            DATABASE.update(displacedate(view_date, -2))

        VIEW.timechart_reset("48h", view_date)
        VIEW.draw_x_labels_48h_view()
        tasks_available = (DATABASE.getdatetasks(displacedate(view_date, -1)) +
                           DATABASE.getdatetasks(view_date) +
                           DATABASE.getdatetasks(displacedate(view_date, -2)))
        VIEW.draw_lines_and_labels(displacedate(view_date, -2).strftime(DATECODE) + " - " +
                                   view_date.strftime(DATECODE), len(tasks_available))
        self.info_content = ""
        self.tasks_showing = []
        self.tasks_loaded = []

        tasks_to_show = {}
        for task_id in tasks_available:
            tasks_to_show[task_id] = DATABASE.cget(task_id, "since_epoch")

        for tooltip in self.tooltips:
            tooltip.destroy()

        self.tooltips = []

        for task_info in sorted(tasks_to_show.iteritems(), key=lambda t: t[1]):
            task_id = task_info[0]

            if DATABASE.cget(task_id, "parent") == "root":
                self.attempt_draw_48h(task_id)

        DATABASE.save_database()
        VIEW.timechart_canvas.config(scrollregion=(0, 0, 0,
                                                   len(self.tasks_showing) * (TASK_WIDTH + 5) + 80))
        VIEW.display_main_details(self.info_content)

    def toggle_debug_mode(self):
        """when toggled on, more development information is provided to the user"""
        if not self.debug_mode:
            dummy_task = model.Task(start_time="Jul 25, 2017 18:00:00")
            self.search_options = dummy_task.args
            self.debug_mode = True
        else:
            self.debug_mode = False
            self.search_options = self.normal_search_options

    def gotodate(self):
        """goes to user specified date"""
        month = VIEW.currentmonth_entry.get()
        day = VIEW.currentday_entry.get()
        year = VIEW.currentyear_entry.get()
        if int(day) < 10:
            day = "0" + str(int(day))
        try:
            date_ = datetime.datetime.strptime(
                " ".join([month, day, year]), "%B %d %Y")
        except ValueError:
            VIEW.current_date_entries_update("INVALID")
            return

        if self.current_mode == "24h":
            date_ = date_ + datetime.timedelta(days=1, seconds=1)
            self.chart_draw_24h(date_)
        elif self.current_mode == "48h":
            date_ = date_ + datetime.timedelta(days=2, seconds=1)
            self.chart_draw_48h(date_)

# =================================================
# ==================== VIEW =======================
# =================================================

class View(object):

    """this class manages the GUI, blindly following the Controller"s commands"""

    def __init__(self):  # pylint: disable=too-many-statements
        self.widget_width = 10

        self.log_sources_editor = None
        self.log_text_box = None

        # -- GUI

        self.view_frame = tk.Frame(
            ROOT,
            height=WINDOW_SIZE[1],
            width=VIEW_FRAME_WIDTH,
            bg="white")
        self.details_frame = tk.Frame(ROOT, width=WINDOW_SIZE[0] - VIEW_FRAME_WIDTH,
                                      height=WINDOW_SIZE[1], bg=DETAILS_BG_COLOR)
        self.canvas_scrollbar = tk.Scrollbar(self.view_frame)
        self.view_canvas = tk.Canvas(self.view_frame, height=WINDOW_SIZE[1],
                                     width=VIEW_FRAME_WIDTH - 17, bg="white")
        self.timechart_canvas = tk.Canvas(self.view_frame, height=WINDOW_SIZE[1] - 67,
                                          width=VIEW_FRAME_WIDTH - 51 - 17,
                                          bg="white", yscrollcommand=self.canvas_scrollbar.set)
        # Placing objects

        self.canvas_scrollbar.config(command=self.timechart_canvas.yview)
        self.view_frame.grid(row=0)
        self.details_frame.grid(row=0, column=1, sticky=tk.N + tk.E + tk.W)
        self.view_canvas.grid(row=0, sticky=tk.N + tk.W)
        self.timechart_canvas.grid(
            row=0, padx=(51, 0),
            pady=(39, 25),
            sticky=tk.N + tk.W)
        self.canvas_scrollbar.grid(
            row=0,
            column=0,
            padx=(VIEW_FRAME_WIDTH - 17,
                  0),
            sticky=tk.N + tk.W + tk.E + tk.S)

        # -- Info Panel --

        self.help_button = tk.Button(self.details_frame, text="Help",
                                     width=self.widget_width, font=FONT,
                                     bg=DETAILS_BG_COLOR)
        self.help_tooltip = ButtonTooltip(self.help_button, HELPSTR)
        self.source_options_button = tk.Button(self.details_frame, text="Edit Log Sources",
                                               width=self.widget_width, font=FONT,
                                               bg=DETAILS_BG_COLOR, command=self.open_log_sources_editor)

        # Placing objects

        self.help_button.grid(row=0, columnspan=2, sticky="nwes", pady=(0, 20))
        self.source_options_button.grid(
            row=0,
            column=2,
            columnspan=4,
            sticky="nwes",
            pady=(
                0,
                20))

        # -- Controller GUI --

        view24_command = lambda: CONTROLLER.chart_draw_24h(view_date=CONTROLLER.current_day -
                                                           datetime.timedelta(
                                                               days=1),
                                                           override=False)
        view48_command = lambda: CONTROLLER.chart_draw_48h(view_date=CONTROLLER.current_day +
                                                           datetime.timedelta(
                                                               days=1),
                                                           override=False)
        self.view24button = tk.Button(self.details_frame, text="24 Hours",
                                      width=self.widget_width, font=FONT,
                                      bg=DETAILS_BG_COLOR,
                                      command=view24_command)
        self.view48button = tk.Button(self.details_frame, text="48 Hours",
                                      width=self.widget_width, font=FONT,
                                      bg=DETAILS_BG_COLOR,
                                      command=view48_command)
        self.updatebutton = tk.Button(self.details_frame, text="Update",
                                      width=self.widget_width, font=FONT,
                                      bg=DETAILS_BG_COLOR,
                                      command=self.open_confirm_update_window)
        self.previousbutton = tk.Button(
            self.details_frame, text="<< Prev",
            width=self.widget_width, font=FONT,
            bg=DETAILS_BG_COLOR,
            command=lambda: CONTROLLER.chart_draw(displacedate(CONTROLLER.current_day, -1)))
        self.nextbutton = tk.Button(
            self.details_frame, text="Next >>",
            width=self.widget_width, font=FONT,
            bg=DETAILS_BG_COLOR,
            command=lambda: CONTROLLER.chart_draw(displacedate(CONTROLLER.current_day, 1)))
        self.debugbutton = tk.Button(self.details_frame, text="Toggle Debug Mode",
                                     width=self.widget_width, font=FONT,
                                     bg=DETAILS_BG_COLOR,
                                     bd=0, command=CONTROLLER.toggle_debug_mode)
        self.currentmonth_entry = tk.Entry(
            self.details_frame,
            font=FONT,
            width=2)
        self.currentday_entry = tk.Entry(
            self.details_frame,
            font=FONT,
            width=2)
        self.currentyear_entry = tk.Entry(
            self.details_frame,
            font=FONT,
            width=2)
        self.gotodate_button = tk.Button(self.details_frame, text="Go", font=FONT, height=1,
                                         bg=DETAILS_BG_COLOR,
                                         command=CONTROLLER.gotodate)
        self.scrollbar = tk.Scrollbar(self.details_frame)
        self.horz_scrollbar = tk.Scrollbar(
            self.details_frame,
            orient=tk.HORIZONTAL)
        self.seperator = tk.Label(self.details_frame,
                                  text="\n{}\n\nDetails:".format("_" * 42),
                                  font=FONT, width=self.widget_width, bg=DETAILS_BG_COLOR)
        self.main_view_mode_button = tk.Button(self.details_frame, text="Return to Main View",
                                               font=FONT, width=self.widget_width,
                                               command=self.info_main_view_mode,
                                               bg=DETAILS_BG_COLOR)
        self.search_entry = tk.Entry(
            self.details_frame,
            width=self.widget_width,
            font=FONT,
            fg="grey")
        self.search_button = tk.Button(self.details_frame, text="Search",
                                       font=FONT, width=self.widget_width,
                                       command=lambda: CONTROLLER.search(""), bg=DETAILS_BG_COLOR)
        self.search_by_label = tk.Label(
            self.details_frame,
            text="Search by: ",
            font=FONT,
            width=self.widget_width)
        self.search_by_button = tk.Button(self.details_frame, text="name", font=FONT,
                                          width=self.widget_width, command=self.change_search_key)
        self.info = tk.Text(self.details_frame, width=20, yscrollcommand=self.scrollbar.set,
                            height=WINDOW_SIZE[1] / 25, font=FONT, bd=0, bg="#f9f9f9",
                            highlightthickness=0, xscrollcommand=self.horz_scrollbar.set,
                            wrap=tk.NONE)

        # -- Placing GUI objects --

        self.scrollbar.grid(row=5, column=5, sticky=tk.N + tk.E + tk.S)
        self.horz_scrollbar.grid(row=6, column=0, columnspan=6, sticky=tk.N + tk.E + tk.W + tk.S,
                                 pady=(5, 0))
        self.main_view_mode_button.grid(
            row=9,
            column=0,
            pady=(10, 0),
            columnspan=6,
            sticky=tk.N + tk.W + tk.E)
        self.search_entry.grid(
            row=7,
            column=0,
            columnspan=6,
            sticky=tk.N + tk.W + tk.E + tk.S,
            pady=(10, 0))
        self.search_button.grid(
            row=8,
            column=0,
            columnspan=2,
            sticky=tk.N + tk.W + tk.E)
        self.search_by_label.grid(
            row=8,
            column=2,
            columnspan=2,
            sticky=tk.N + tk.E + tk.S + tk.W)
        self.search_by_button.grid(
            row=8,
            column=4,
            columnspan=2,
            sticky=tk.N + tk.W + tk.E)

        self.view24button.grid(
            row=1,
            columnspan=2,
            column=0,
            sticky=tk.N +
            tk.W +
            tk.E)
        self.view48button.grid(
            row=1,
            column=2,
            columnspan=2,
            sticky=tk.N +
            tk.W +
            tk.E)
        self.updatebutton.grid(
            row=1,
            column=4,
            columnspan=2,
            sticky=tk.N +
            tk.W +
            tk.E)
        self.previousbutton.grid(
            row=2,
            columnspan=3,
            column=0,
            sticky=tk.N + tk.W + tk.E)
        self.nextbutton.grid(
            row=2,
            column=3,
            columnspan=3,
            sticky=tk.N +
            tk.W +
            tk.E)
        self.debugbutton.grid(
            row=10,
            column=0,
            columnspan=3,
            sticky=tk.N + tk.W + tk.E,
            pady=(10, 10))

        self.currentmonth_entry.grid(
            row=3,
            column=0,
            columnspan=2,
            sticky=tk.N + tk.W + tk.E + tk.S)
        self.currentday_entry.grid(
            row=3,
            column=2,
            columnspan=1,
            sticky=tk.N + tk.W + tk.E + tk.S)
        self.currentyear_entry.grid(
            row=3,
            column=3,
            columnspan=2,
            sticky=tk.N + tk.W + tk.E + tk.S)
        self.gotodate_button.grid(
            row=3,
            column=5,
            columnspan=1,
            sticky=tk.N + tk.W + tk.E)

        self.seperator.grid(
            row=4,
            column=0,
            columnspan=6,
            sticky=tk.N +
            tk.W + tk.E)
        self.info.grid(
            row=5,
            column=0,
            columnspan=6,
            sticky=tk.N + tk.W + tk.E,
            padx=(5, 17))

        # -- GUI objects config --

        self.info.bind("<1>", lambda event: self.info.focus_set())

        self.search_entry.insert(tk.END, "Search")
        self.scrollbar.config(command=self.info.yview)
        self.horz_scrollbar.config(command=self.info.xview)
        self.info.config(state=tk.NORMAL)
        self.info.delete("1.0", tk.END)
        self.info.insert(tk.END, "LOADING...")
        self.info.config(state=tk.DISABLED)
        self.current_date_entries_update(displacedate(today(), -1))
        self.search_entry.bind("<1>", self.clear_search_box)

        # ROOT.bind("<Configure>", on_resize)

    def open_log_file(self, filepath):
        """opens a window with the contents of the file provided"""
        log_file_viewer = tk.Tk()
        log_file_viewer.title(filepath)

        top_frame = tk.Frame(log_file_viewer)
        bottom_frame = tk.Frame(log_file_viewer)
        top_frame.pack(expand=True, fill="both")
        bottom_frame.pack(fill="x")

        vert_scrollbar = tk.Scrollbar(top_frame)
        horz_scrollbar = tk.Scrollbar(bottom_frame, orient="horizontal")

        text_box = tk.Text(top_frame, wrap="none",
                           highlightthickness=0,
                           bg="#f9f9f9",
                           yscrollcommand=vert_scrollbar.set,
                           xscrollcommand=horz_scrollbar.set)

        vert_scrollbar.config(command=text_box.yview)
        horz_scrollbar.config(command=text_box.xview)

        text_box.pack(expand=True, fill="both", side="left")
        vert_scrollbar.pack(fill="y", side="right")
        horz_scrollbar.pack(fill="x", side="bottom")
        with open(filepath, "r") as logfile:
            text_box.insert("end", logfile.read())
        text_box.config(state=tk.DISABLED)
        text_box.bind("<1>", lambda event: text_box.focus_set())

    def open_log_sources_editor(self):
        """opens the log sources editor"""
        if self.log_sources_editor is not None:
            self.log_sources_editor_close(save=True)
        self.log_sources_editor = tk.Tk()
        self.log_sources_editor.title("Log Sources Editor")

        button_frame = tk.Frame(self.log_sources_editor)
        editor_frame = tk.Frame(self.log_sources_editor)

        button_frame.pack(fill="x")
        editor_frame.pack(expand=True, fill="both")

        addfile_button = tk.Button(button_frame, text="Add Another File",
                                   command=self.add_log_source)
        close_button = tk.Button(button_frame, text="Close",
                                 command=self.log_sources_editor_close)
        saveandclose_button = tk.Button(
            button_frame, text="Save & Close",
            command=lambda: self.log_sources_editor_close(True))
        self.log_text_box = tk.Text(editor_frame,
                                    highlightthickness=0, bg="#f9f9f9")

        addfile_button.pack(side="left", anchor="w")
        saveandclose_button.pack(side="right", anchor="e")
        close_button.pack(side="right", anchor="e")
        self.log_text_box.pack(expand=True, fill="both", side="bottom")

        with open(LOG_SOURCES_FILE, "r") as txtfile:
            files = [line.strip() for line in txtfile.readlines()]
            if files[-1] == "":
                del files[-1]
            self.log_text_box.insert("end", "\n".join(files))

    def add_log_source(self):
        """add a filepath to the log sources"""
        filepath = tkFileDialog.askopenfilename(title="Select File",
                                                filetypes=(("all files", "*.*"),
                                                           ("log files", "*.log")))
        self.log_sources_editor_close(save=True)
        self.open_log_sources_editor()
        files = self.log_text_box.get("1.0", "end").split("\n")
        if files[-1] == "":
            del files[-1]
        files.append(filepath)
        self.log_text_box.delete("1.0", "end")
        self.log_text_box.insert("end", "\n".join(files))

    def log_sources_editor_close(self, save=False):
        """closes the log sources editor"""
        if save:
            with open(LOG_SOURCES_FILE, "w") as txtfile:
                box_content = self.log_text_box.get("1.0", "end")
                if box_content[-1] == "\n":
                    box_content = box_content[:-1]
                txtfile.write(box_content)
        self.log_sources_editor.destroy()
        self.log_sources_editor = None

    def open_confirm_update_window(self):
        """alerts the user of the risks of updating and asks if user is sure"""
        if CONTROLLER.current_mode == "24h":
            first_day = CONTROLLER.current_day.replace(hour=18, minute=0,
                                                       second=0,
                                                       microsecond=0) - datetime.timedelta(days=1)
        elif CONTROLLER.current_mode == "48h":
            first_day = CONTROLLER.current_day.replace(hour=18, minute=0,
                                                       second=0,
                                                       microsecond=0) - datetime.timedelta(days=2)
        last_day = CONTROLLER.current_day.replace(
            hour=18,
            minute=0,
            second=0,
            microsecond=0)
        display_text = """\
Updating will delete all tasks between \
{} and {} \
to make room for the new tasks.\n
Are you sure you want to continue?""".format(first_day.strftime("%B %d, %Y %H:%M:%S"),
                                             last_day.strftime("%B %d, %Y %H:%M:%S"))
        if tkMessageBox.askyesno("Are you sure?", display_text,
                                 icon=tkMessageBox.WARNING):
            CONTROLLER.parseupdate()

    def open_resize_window(self):  # pylint: disable=no-self-use
        """alerts the user of further action needed in order to resize the window"""
        toplevel = tk.Toplevel(
            self.timechart_canvas,
            bd=1,
            relief="solid",
            bg="#FFFFFF")
        CONTROLLER.tooltips.append(toplevel)

        x_pos = ROOT.winfo_x() + 50
        y_pos = ROOT.winfo_y() + 50

        toplevel.wm_overrideredirect(True)
        toplevel.wm_geometry("+%d+%d" % (x_pos, y_pos))
        resize_label = tk.Label(toplevel, text="Changes detected\nRestart to Apply",
                                relief="solid",
                                font=TASK_FONT)
        resize_label.grid(
            row=0,
            sticky=tk.N +
            tk.W +
            tk.S,
            pady=(
                5,
                0),
            padx=(
                3,
                0))

    def scroll_canvas(self, event):
        """scrolls the canvas when the mouse scroll wheel is used"""
        height = self.timechart_canvas.winfo_height()
        items_height = self.timechart_canvas.bbox(tk.ALL)
        direction = 0
        if event.num == 5 or event.delta == -120:
            direction = 1
        if event.num == 4 or event.delta == 120:
            direction = -1
        if items_height < height:
            direction = 0

        self.timechart_canvas.yview_scroll(direction, "units")

    def info_insert(self, text, hiddentext=None):
        """inserts provided info into the details window"""
        self.info.config(state=tk.NORMAL)
        self.info.delete(1.0, tk.END)

        if "logfile" in text:
            for line in text.split("\n"):
                if "logfile" in line:
                    filepath = line.strip().replace("logfile: ", "")
                    hyperlink = HyperlinkManager(self.info)
                    self.info.insert("end", "logfile: ")
                    self.info.insert(
                        "end",
                        filepath,
                        hyperlink.add(lambda: self.open_log_file(filepath)))
                    self.info.insert("end", "\n")
                else:
                    self.info.insert(tk.END, line + "\n")
        else:
            self.info.insert(tk.END, "\n" + text)

        if hiddentext is not None and CONTROLLER.debug_mode:
            self.info.insert(tk.END, hiddentext)

        self.info.config(state=tk.DISABLED)

    def select_task(self, task_id, move=True):
        """scrolls to the given task and highlights it"""
        if move:
            new_buffer = WINDOW_SIZE[1] - 67
            if DATABASE.cget(task_id, "y_pos") < WINDOW_SIZE[1] - 67:
                new_buffer = 0
            else:
                new_buffer = DATABASE.cget(task_id, "y_pos")
            point_to_move = float(new_buffer + 1) / (len(CONTROLLER.tasks_showing) *
                                                     (TASK_WIDTH + 5) + WINDOW_SIZE[1] / 2)
            self.timechart_canvas.yview_moveto(point_to_move)
        self.timechart_canvas.itemconfig("task", width=0)
        self.timechart_canvas.itemconfig(
            DATABASE.cget(
                task_id,
                "graphical_id"),
            width=5)

    def display_main_details(self, info_content):
        """displays information about all the tasks displayed"""
        self.info.config(state=tk.NORMAL)
        self.info.delete("1.0", tk.END)
        info_content = "Tasks displayed: " + str(len(CONTROLLER.tasks_showing)) + \
            "\n" + info_content
        self.info.insert(tk.END, info_content)
        self.info.config(state=tk.DISABLED)

        self.currentmonth_entry.config(state=tk.NORMAL)
        self.currentday_entry.config(state=tk.NORMAL)
        self.currentyear_entry.config(state=tk.NORMAL)
        self.gotodate_button.config(state=tk.NORMAL)

    def current_date_entries_update(self, date_):
        """inserts the provided date into the entries showing the current date"""
        if date_ == "INVALID":
            self.currentmonth_entry.delete(0, tk.END)
            self.currentday_entry.delete(0, tk.END)
            self.currentyear_entry.delete(0, tk.END)
            self.currentmonth_entry.insert(0, "Invalid")
            self.currentday_entry.insert(0, "Date")
            self.currentyear_entry.insert(0, "Entered")

            if CONTROLLER.current_mode == "24h":
                days_diff = 1
            elif CONTROLLER.current_mode == "48h":
                days_diff = 2

            return_date = CONTROLLER.current_day - \
                datetime.timedelta(days=days_diff)

            ROOT.after(
                2000,
                lambda: self.current_date_entries_update(return_date))
            return

        month = date_.strftime("%B")
        day = date_.strftime("%d")
        year = date_.strftime("%Y")

        if int(day) < 10:
            day = day[1:]
        self.currentmonth_entry.delete(0, tk.END)
        self.currentday_entry.delete(0, tk.END)
        self.currentyear_entry.delete(0, tk.END)
        self.currentmonth_entry.insert(0, month)
        self.currentday_entry.insert(0, day)
        self.currentyear_entry.insert(0, year)

    def clear_search_box(self, event):
        """clears the search box on first click"""
        if CONTROLLER.search_box_first_click:
            self.search_entry.delete(0, tk.END)
            self.search_entry.config(fg="black")
            CONTROLLER.search_box_first_click = False

    def change_search_key(self, search_by_toplevel=None, listbox=None):
        """changes what task element to search for in the search method (i.e. name, duration,
        task ID, etc.)"""
        if search_by_toplevel is None:
            if not CONTROLLER.search_option_active:
                search_by_toplevel = tk.Toplevel(
                    self.details_frame,
                    bg="white",
                    bd=1,
                    relief="solid")
                search_by_toplevel.wm_overrideredirect(True)
                x_pos = self.search_by_button.winfo_rootx()
                y_pos = self.search_by_button.winfo_rooty()
                width = self.search_by_button.winfo_width()
                height = 200
                search_by_toplevel.wm_geometry("%dx%d" % (width, height))
                search_by_toplevel.wm_geometry("+%d+%d" % (x_pos, y_pos))
                ratio = 9
                listbox = tk.Listbox(
                    search_by_toplevel,
                    width=ratio,
                    font=FONT)
                for key in CONTROLLER.search_options:
                    listbox.insert(tk.END, key.replace("_", " "))
                close_button = tk.Button(search_by_toplevel, font=FONT, text="Choose", width=ratio,
                                         command=lambda: self.change_search_key(search_by_toplevel,
                                                                                listbox))
                listbox.grid(row=0, sticky=tk.N + tk.E + tk.W + tk.S)
                close_button.grid(row=1, sticky=tk.N + tk.E + tk.W)
                CONTROLLER.search_option_active = True
        else:
            if CONTROLLER.search_option_active:
                try:
                    CONTROLLER.search_by_term = str(
                        listbox.get(
                            listbox.curselection()))
                except tk.TclError:
                    pass
                new_text = "{}".format(
                    CONTROLLER.search_by_term.replace(
                        "_",
                        " "))
                self.search_by_button.config(text=new_text)
                search_by_toplevel.destroy()
                CONTROLLER.search_option_active = False

    def info_main_view_mode(self):
        """returns to viewing details about the whole page after focusing on a task or after a
        search"""
        self.timechart_canvas.itemconfig("task", width=0)
        self.display_main_details(CONTROLLER.info_content)

    def draw_lines_and_labels(self, title, total_task_count):
        """draws gridlines, axes, labels, and title"""
        seperation = int((VIEW_FRAME_WIDTH - 50) / 24)
        # Gridlines
        gridline_count = 24
        for j in range(gridline_count):
            if j == 0:
                self.view_canvas.create_line(
                    50, 40,
                    50, WINDOW_SIZE[1] - 5,
                    fill="black")
                continue
            x_pos = j * seperation + 50
            self.view_canvas.create_line(
                x_pos, 40,
                x_pos, WINDOW_SIZE[1] - 5,
                fill="grey")
            if total_task_count * TASK_WIDTH < WINDOW_SIZE[1]:
                grid_line_height = WINDOW_SIZE[1]
            else:
                grid_line_height = total_task_count * TASK_WIDTH + 100
            self.timechart_canvas.create_line(x_pos - 50, -100, x_pos - 50, grid_line_height,
                                              fill="grey")

        if CONTROLLER.current_mode == "24h":
            first_day = (CONTROLLER.current_day - datetime.timedelta(days=1)).replace(hour=12,
                                                                                      minute=0,
                                                                                      second=0)
            second_count = 86400
        elif CONTROLLER.current_mode == "48h":
            first_day = (CONTROLLER.current_day - datetime.timedelta(days=2)).replace(hour=12,
                                                                                      minute=0,
                                                                                      second=0)
            second_count = 172800
        last_day = CONTROLLER.current_day.replace(hour=12, minute=0, second=0)
        if since_epoch(first_day) < since_epoch(
                today()) < since_epoch(last_day):
            x_pos = (today() - first_day).total_seconds() * \
                (VIEW_FRAME_WIDTH - 54) / second_count
            self.timechart_canvas.create_line(x_pos, -100, x_pos, grid_line_height, fill="blue",
                                              tags="nontask")

        # Axes
        self.view_canvas.create_line(50, WINDOW_SIZE[1] - 25, VIEW_FRAME_WIDTH, WINDOW_SIZE[1] - 25,
                                     width=5, tags="nontask")
        self.view_canvas.create_line(
            50, 40,
            50, WINDOW_SIZE[1] - 25,
            width=5, tags="nontask")

        # Title
        self.view_canvas.create_text(VIEW_FRAME_WIDTH / 2, 20, tags="nontask", fill="black",
                                     font=BIG_FONT,
                                     text=title)
        self.view_canvas.create_text(10, 10, tags="nontask", fill="black", font=TASK_FONT,
                                     text="v " + VERSION, anchor=tk.N + tk.W)
        # Y Label
        self.view_canvas.create_text(25, WINDOW_SIZE[1] / 2, tags="nontask", font=BIG_FONT,
                                     text="\n".join(list("Tasks")))

    def draw_x_labels_48h_view(self):
        """draws the time labels on the x axis for the 24h view"""
        seperation = int((VIEW_FRAME_WIDTH - 50) / 24)
        label_count = 0
        for j in range(6, 12):
            time_label = str(j * 2) + ":00"
            self.view_canvas.create_text(label_count * seperation + 52,
                                         WINDOW_SIZE[1] - 20, anchor=tk.N + tk.W,
                                         fill="black",
                                         text=time_label, font=FONT,
                                         tags="nontask")
            label_count += 1
        for j in range(0, 12):
            if j * 2 < 10:
                time_label = "0" + str(j * 2) + ":00"
            else:
                time_label = str(j * 2) + ":00"
            self.view_canvas.create_text(label_count * seperation + 52,
                                         WINDOW_SIZE[1] - 20, anchor=tk.N + tk.W,
                                         fill="black",
                                         text=time_label, font=FONT,
                                         tags="nontask")
            label_count += 1
        for j in range(0, 6):
            if j * 2 < 10:
                time_label = "0" + str(j * 2) + ":00"
            else:
                time_label = str(j * 2) + ":00"
            self.view_canvas.create_text(label_count * seperation + 52,
                                         WINDOW_SIZE[1] - 20, anchor=tk.N + tk.W,
                                         fill="black",
                                         text=time_label, font=FONT,
                                         tags="nontask")
            label_count += 1

    def draw_x_labels_24h_view(self):
        """draws the time labels on the x axis for the 48h view"""
        seperation = int((VIEW_FRAME_WIDTH - 50) / 24)
        label_count = 0
        for j in range(12, 24):
            time_label = str(j) + ":00"
            self.view_canvas.create_text(label_count * seperation + 52,
                                         WINDOW_SIZE[1] - 20, anchor=tk.N + tk.W,
                                         fill="black",
                                         text=time_label, font=FONT,
                                         tags="nontask")
            label_count += 1
        for j in range(0, 12):
            if j < 10:
                time_label = "0" + str(j) + ":00"
            else:
                time_label = str(j) + ":00"
            self.view_canvas.create_text(label_count * seperation + 52,
                                         WINDOW_SIZE[1] - 20, anchor=tk.N + tk.W,
                                         fill="black",
                                         text=time_label, font=FONT,
                                         tags="nontask")
            label_count += 1

    def draw_markers_24h_view(self, view_date, task_id):
        """draws all the markers and error markers of a given task"""
        y_pos = len(CONTROLLER.tasks_showing) * (TASK_WIDTH + 5)
        marker_ids = []

        children = DATABASE.get_all_children(task_id)
        for child_id in children:
            marker_date = extractdate(DATABASE.cget(child_id, "start_time"))
            marker = datetime.datetime.strptime(
                DATABASE.cget(
                    child_id,
                    "start_time"),
                DATETIMECODE)
            is_one_day_ago = marker_date == displacedate(view_date,
                                                         -1).strftime(DATECODE)
            is_viewed_date = marker_date == view_date.strftime(DATECODE)
            if is_one_day_ago and secs_since_midnight(marker) >= 43200:
                marker_seconds = secs_since_midnight(marker) - 43200
            elif is_viewed_date and secs_since_midnight(marker) < 43200:
                marker_seconds = secs_since_midnight(marker) + 43200
            else:
                marker_seconds = None
            if marker_seconds is not None:
                marker_seconds = (
                    marker_seconds / 86400.0) * (VIEW_FRAME_WIDTH - 50)
                mark_id = self.timechart_canvas.create_rectangle(marker_seconds, y_pos,
                                                                 marker_seconds +
                                                                 5,
                                                                 y_pos +
                                                                 TASK_WIDTH,
                                                                 fill="#828282",
                                                                 width=0, tags="task")
                marker_ids.append(mark_id)

        children.append(task_id)
        for child_id in children:
            if not DATABASE.cget(child_id, "errors") is None:
                for error_info in DATABASE.cget(child_id, "errors"):
                    e_marker_date = extractdate(error_info[0])
                    e_marker = datetime.datetime.strptime(
                        error_info[0],
                        DATETIMECODE)
                    is_one_day_ago = e_marker_date == displacedate(view_date,
                                                                   -1).strftime(DATECODE)
                    is_viewed_date = e_marker_date == view_date.strftime(
                        DATECODE)
                    if is_one_day_ago and secs_since_midnight(
                            e_marker) >= 43200:
                        e_marker_seconds = secs_since_midnight(
                            e_marker) - 43200
                    elif is_viewed_date and secs_since_midnight(e_marker) < 43200:
                        e_marker_seconds = secs_since_midnight(
                            e_marker) + 43200
                    else:
                        e_marker_seconds = None

                    if e_marker_seconds is not None:
                        e_marker_seconds = (
                            e_marker_seconds / 86400.0) * (VIEW_FRAME_WIDTH - 50)
                        mark_id = self.timechart_canvas.create_rectangle(e_marker_seconds, y_pos,
                                                                         e_marker_seconds +
                                                                         5,
                                                                         y_pos +
                                                                         TASK_WIDTH,
                                                                         fill="#FF2332",
                                                                         width=0, tags="task")
                        marker_ids.append(mark_id)

        DATABASE.hidden_config(task_id, marker_ids=marker_ids)

    def timechart_reset(self, mode, view_date):
        """resets the timechart canvas"""
        if mode == "24h":
            self.current_date_entries_update(displacedate(view_date, -1))
        elif mode == "48h":
            self.current_date_entries_update(displacedate(view_date, -2))

        self.currentmonth_entry.config(state=tk.DISABLED)
        self.currentday_entry.config(state=tk.DISABLED)
        self.currentyear_entry.config(state=tk.DISABLED)
        self.gotodate_button.config(state=tk.DISABLED)
        ROOT.update()

        CONTROLLER.current_mode = mode
        CONTROLLER.current_day = view_date
        self.timechart_canvas.delete("task")
        self.timechart_canvas.delete("nontask")
        self.view_canvas.delete("nontask")

    def draw_task(self, task_id, x_pos, width, y_pos):
        """draws a task"""
        x_pos += 4
        obj = self.timechart_canvas.create_rectangle(x_pos, y_pos,
                                                     x_pos +
                                                     width,
                                                     y_pos +
                                                     TASK_WIDTH,
                                                     dash=(10, 20),
                                                     fill=DATABASE.cget(
                                                         task_id,
                                                         "color"),
                                                     width=0, tags="task")
        if CONTROLLER.current_mode == "24h":
            self.draw_markers_24h_view(CONTROLLER.current_day, task_id)
        else:
            self.draw_markers_48h_view(CONTROLLER.current_day, task_id)

        if len(str(DATABASE.cget(task_id, "name"))) * \
                9 - 1 <= width - 5:
            textobj = self.timechart_canvas.create_text(x_pos + 5,
                                                        y_pos +
                                                        (TASK_WIDTH /
                                                         2),
                                                        tags="task",
                                                        fill=COLORS[DATABASE.cget(task_id,
                                                                                  "color")],
                                                        font=TASK_FONT,
                                                        text=str(DATABASE.cget(task_id,
                                                                               "name")),
                                                        anchor=tk.W)
        else:
            textobj = self.timechart_canvas.create_text(x_pos + width + 5,
                                                        y_pos +
                                                        (TASK_WIDTH /
                                                         2),
                                                        tags="task",
                                                        fill="black", font=TASK_FONT,
                                                        text=str(DATABASE.cget(task_id,
                                                                               "name")),
                                                        anchor=tk.W)
        return obj, textobj

    def draw_markers_48h_view(self, view_date, task_id):
        """draws all the markers of a given task"""
        y_pos = len(CONTROLLER.tasks_showing) * (TASK_WIDTH + 5)
        marker_ids = []

        children = DATABASE.get_all_children(task_id)
        for child_id in children:
            marker_date = extractdate(DATABASE.cget(child_id, "start_time"))
            marker = datetime.datetime.strptime(
                DATABASE.cget(
                    child_id,
                    "start_time"),
                DATETIMECODE)
            is_two_days_ago = marker_date == displacedate(view_date,
                                                          -2).strftime(DATECODE)
            is_one_day_ago = marker_date == displacedate(view_date,
                                                         -1).strftime(DATECODE)
            is_viewed_date = marker_date == view_date.strftime(DATECODE)
            if is_two_days_ago and secs_since_midnight(marker) >= 43200:
                marker_seconds = secs_since_midnight(marker) - 43200
            elif is_one_day_ago:
                marker_seconds = secs_since_midnight(marker) + 43200
            elif is_viewed_date and secs_since_midnight(marker) < 43200:
                marker_seconds = secs_since_midnight(marker) + 129600
            else:
                marker_seconds = None

            if marker_seconds is not None:
                marker_seconds = (
                    marker_seconds / 172800.0) * (VIEW_FRAME_WIDTH - 50)
                mark_id = self.timechart_canvas.create_rectangle(marker_seconds, y_pos,
                                                                 marker_seconds +
                                                                 5,
                                                                 y_pos +
                                                                 TASK_WIDTH,
                                                                 fill="#828282",
                                                                 width=0, tags="task")
                marker_ids.append(mark_id)

        children.append(task_id)
        for child_id in children:
            if not DATABASE.cget(child_id, "errors") is None:
                for error_info in DATABASE.cget(child_id, "errors"):
                    e_marker_date = extractdate(error_info[0])
                    e_marker = datetime.datetime.strptime(
                        error_info[0],
                        DATETIMECODE)
                    is_two_days_ago = e_marker_date == displacedate(view_date,
                                                                    -2).strftime(DATECODE)
                    is_one_day_ago = e_marker_date == displacedate(view_date,
                                                                   -1).strftime(DATECODE)
                    is_viewed_date = e_marker_date == view_date.strftime(
                        DATECODE)
                    if is_two_days_ago and secs_since_midnight(
                            e_marker) >= 43200:
                        e_marker_seconds = secs_since_midnight(
                            e_marker) - 43200
                    elif is_one_day_ago:
                        e_marker_seconds = secs_since_midnight(
                            e_marker) + 43200
                    elif is_viewed_date and secs_since_midnight(e_marker) < 43200:
                        e_marker_seconds = secs_since_midnight(
                            e_marker) + 129600
                    else:
                        e_marker_seconds = None

                    if e_marker_seconds is not None:
                        e_marker_seconds = (
                            e_marker_seconds / 172800.0) * (VIEW_FRAME_WIDTH - 50)
                        mark_id = self.timechart_canvas.create_rectangle(e_marker_seconds, y_pos,
                                                                         e_marker_seconds +
                                                                         5,
                                                                         y_pos +
                                                                         TASK_WIDTH,
                                                                         fill="#FF2332",
                                                                         width=0, tags="task")
                        marker_ids.append(mark_id)
        DATABASE.hidden_config(task_id, marker_ids=marker_ids)

    def final_execution(self):
        """conducts the final execution of the file"""
        ROOT.after(100, lambda: CONTROLLER.chart_draw_24h(today()))
        ROOT.bind("<Return>", CONTROLLER.search)
        self.timechart_canvas.bind("<MouseWheel>", self.scroll_canvas)
        self.timechart_canvas.bind("<Button-4>", self.scroll_canvas)
        self.timechart_canvas.bind("<Button-5>", self.scroll_canvas)
        self.timechart_canvas.bind("<1>", CONTROLLER.canvas_click)
        ROOT.mainloop()

class TaskTooltip(object):

    """creates a popup window when hovering over a task
    - adapted from stackoverflow.com"""

    def __init__(self, task_id):
        self.graphical_id = DATABASE.cget(task_id, "graphical_id")
        self.text_id = DATABASE.cget(task_id, "text_graphical_id")
        self.task_id = task_id
        self.toplevel = None

        VIEW.timechart_canvas.tag_bind(
            self.graphical_id,
            "<Enter>",
            self.showtip)
        VIEW.timechart_canvas.tag_bind(
            self.graphical_id,
            "<Leave>",
            self.hidetip)
        VIEW.timechart_canvas.tag_bind(self.graphical_id, "<1>", self.hidetip)
        VIEW.timechart_canvas.tag_bind(self.graphical_id, "<Leave>",
                                       CONTROLLER.enable_tooltips, "+")
        VIEW.timechart_canvas.tag_bind(self.text_id, "<Enter>", self.showtip)
        VIEW.timechart_canvas.tag_bind(self.text_id, "<Leave>", self.hidetip)
        VIEW.timechart_canvas.tag_bind(self.text_id, "<1>", self.hidetip)
        VIEW.timechart_canvas.tag_bind(
            self.text_id,
            "<Leave>",
            CONTROLLER.enable_tooltips,
            "+")

        for marker_id in DATABASE.cget(self.task_id, "marker_ids"):
            VIEW.timechart_canvas.tag_bind(marker_id, "<Enter>", self.showtip)
            VIEW.timechart_canvas.tag_bind(marker_id, "<Leave>", self.hidetip)
            VIEW.timechart_canvas.tag_bind(marker_id, "<1>", self.hidetip)
            VIEW.timechart_canvas.tag_bind(
                marker_id,
                "<Leave>",
                CONTROLLER.enable_tooltips,
                "+")

        markers = DATABASE.cget(self.task_id, "children")
        e_markers = DATABASE.cget(self.task_id, "errors")
        self.name = DATABASE.cget(self.task_id, "name")
        self.text = """Start time: {}
Duration: {}
Child tasks: {}
Errors: {}""".format(DATABASE.cget(self.task_id, "start_time"),
                     DATABASE.cget(self.task_id, "duration"),
                     len(markers),
                     0 if e_markers is None else len(e_markers))

    def showtip(self, event):
        """shows information when a task is hovered over"""
        if not CONTROLLER.tooltip_enabled:
            return

        start_date = extractdate(DATABASE.cget(self.task_id, "start_time"))
        start_time = datetime.datetime.strptime(DATABASE.cget(self.task_id, "start_time"),
                                                DATETIMECODE)
        is_one_day_ago = start_date == displacedate(
            CONTROLLER.current_day, -1).strftime(DATECODE)
        is_two_days_ago = start_date == displacedate(
            CONTROLLER.current_day, -2).strftime(DATECODE)
        start_secs_since_midnight = secs_since_midnight(start_time)
        orig_x_pos = DATABASE.cget(self.task_id, "x_pos")
        orig_y_pos = DATABASE.cget(self.task_id, "y_pos")
        if start_secs_since_midnight < 43200:
            if is_two_days_ago:
                orig_x_pos = 0
            elif is_one_day_ago and CONTROLLER.current_mode == "24h":
                orig_x_pos = 0

        x_pos = ROOT.winfo_x() + 51
        y_pos = ROOT.winfo_y() + 39
        x_pos += (orig_x_pos - VIEW.timechart_canvas.canvasx(0)) + 4
        y_pos += (orig_y_pos - VIEW.timechart_canvas.canvasy(0)) + \
            TASK_WIDTH + 5

        # creates a toplevel window
        self.toplevel = tk.Toplevel(
            VIEW.timechart_canvas,
            bd=1,
            relief="solid",
            bg="#FFFFFF")
        CONTROLLER.tooltips.append(self.toplevel)
        self.toplevel.wm_overrideredirect(True)
        self.toplevel.wm_geometry("+%d+%d" % (x_pos, y_pos))
        name_label = tk.Label(self.toplevel, text=self.name, justify="left",
                              background="#ffffff", relief="solid", bd=0, anchor=tk.W,
                              font=(TASK_FONT[0], TASK_FONT[1], FONT_BOLD[2]))
        info_label = tk.Label(self.toplevel, text=self.text, justify="left",
                              background="#ffffff", relief="solid", bd=0, anchor=tk.W,
                              font=TASK_FONT, width=60)
        name_label.grid(
            row=0,
            sticky=tk.N +
            tk.W +
            tk.S,
            pady=(
                5,
                0),
            padx=(
                3,
                0))
        info_label.grid(
            row=1,
            sticky=tk.N +
            tk.W +
            tk.S,
            pady=(
                0,
                5),
            padx=(
                3,
                0))

    def hidetip(self, event):
        """removed the hover information when task is no longer hovered over"""
        if self.toplevel:
            self.toplevel.destroy()

class ButtonTooltip(object):
    """Similar to TaskTooltip, but for tk.Button widgets"""
    def __init__(self, widget, text):
        self.widget = widget
        self.tipwindow = None
        self.widget_id = None
        self.x_pos = self.y_pos = 0
        self.text = text
        self._id1 = self.widget.bind("<1>", self.click)
        self._id2 = self.widget.bind("<Leave>", self.leave)

    def click(self, event=None):
        """event when cursor clicks on button """
        self.schedule()

    def leave(self, event=None):
        """event when the cursor leaves the button"""
        self.unschedule()
        self.hidetip()

    def schedule(self):
        """queues the tooltip to be displayed"""
        self.unschedule()
        self.widget_id = self.widget.after(0, self.showtip)

    def unschedule(self):
        """removes the tooltip from the queue"""
        if self.widget_id:
            self.widget.after_cancel(self.widget_id)
        self.widget_id = None

    def showtip(self):
        """displays the tooltip"""
        if self.tipwindow:
            return
        # The tip window must be completely outside the button;
        # otherwise when the mouse enters the tip window we get
        # a leave event and it disappears, and then we get an enter
        # event and it reappears, and so on forever :-(
        x_pos = self.widget.winfo_rootx() + 20
        y_pos = self.widget.winfo_rooty() + self.widget.winfo_height() + 1
        self.tipwindow = tk.Toplevel(self.widget)
        self.tipwindow.wm_overrideredirect(1)
        self.tipwindow.wm_geometry("+%d+%d" % (x_pos, y_pos))
        self.showcontents()

    def showcontents(self, text="Your text here"):
        """displays the tooltip's contents"""
        label = tk.Label(self.tipwindow, text=self.text, justify=tk.LEFT,
                         background="#ffffff", relief=tk.SOLID, borderwidth=1)
        label.pack()

    def hidetip(self):
        """removes the tooltip"""
        if self.tipwindow:
            self.tipwindow.destroy()
        self.tipwindow = None

class HyperlinkManager(object):
    """Hyper link object that can be inserted into tk.Text widgets"""
    def __init__(self, text):

        self.text = text

        self.text.tag_config("hyper", foreground="blue", underline=1)

        self.text.tag_bind("hyper", "<Enter>", self._enter)
        self.text.tag_bind("hyper", "<Leave>", self._leave)
        self.text.tag_bind("hyper", "<Button-1>", self._click)

        self.reset()

    def reset(self):
        """removes all links"""
        self.links = {}

    def add(self, action):
        """adds a link"""
        # add an action to the manager.  returns tags to use in
        # associated text widget
        tag = "hyper-%d" % len(self.links)
        self.links[tag] = action
        return "hyper", tag

    def _enter(self, event):
        """changes cursor when its hovering over the text"""
        self.text.config(cursor="hand2")

    def _leave(self, event):
        """returns the cursor to normal when it exits the text"""
        self.text.config(cursor="")

    def _click(self, event):
        """activates link when clicked on"""
        for tag in self.text.tag_names(tk.CURRENT):
            if tag[:6] == "hyper-":
                self.links[tag]()
                return

if __name__ == "__main__":

    DATABASE = model.Model()

    CONTROLLER = Controller()
    ROOT = tk.Tk()
    ROOT.geometry(str(WINDOW_SIZE[0]) + "x" + str(WINDOW_SIZE[1]))
    # ROOT.resizable(width=False, height=False)
    ROOT.title("Night Vision")
    ROOT.configure(bg=DETAILS_BG_COLOR)

    COLORS = definecolors()
    VIEW = View()
    VIEW.final_execution()

