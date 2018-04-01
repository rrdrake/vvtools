#!/usr/bin/env python

# Copyright 2018 National Technology & Engineering Solutions of Sandia, LLC
# (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S.
# Government retains certain rights in this software.

'''testing the ../model.py module'''
# pylint: disable=import-error
import sys
import os
import datetime
import shutil
import json
import unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir))

import model  # nopep8 Suppress E402

LOG_SOURCES_FILE = os.path.join("resources", "log_sources.txt")


class TestModelTask(unittest.TestCase):

    '''testing the Task class ( and a function )'''

    def setUp(self):
        '''setting up fixations'''
        self.database = model.Model()
        self.task = model.Task(start_time="Jun 28, 2017 15:18:38")
        self.task_id = self.task.information['task_id']

    def tearDown(self):
        '''tearing down fixations'''
        del self.database
        del self.task

    def test_extractdate(self):
        '''testing the extractdate function'''
        input_date = "Jun 28, 2017 15:18:38"
        expected_date = "Jun 28, 2017"
        self.assertEqual(model.extractdate(input_date), expected_date)

    def test_is_valid_start_time_false(self):
        '''testing the valid_start_time method, expecting an output of false'''
        date_ = datetime.datetime(2017, 7, 17, 12, 0, 0)
        first_date = datetime.datetime(2017, 7, 18, 12, 0, 0)
        last_date = datetime.datetime(2017, 7, 19, 12, 0, 0)
        self.assertFalse(
            model.is_valid_start_time(
                date_,
                first_date,
                last_date))

    def test_is_valid_start_time_true(self):
        '''testing the valid_start_time method, expecting an output of true'''
        date_ = datetime.datetime(2017, 7, 18, 18, 0, 0)
        first_date = datetime.datetime(2017, 7, 18, 18, 0, 0)
        last_date = datetime.datetime(2017, 7, 19, 18, 0, 0)
        self.assertTrue(
            model.is_valid_start_time(
                date_,
                first_date,
                last_date))

    def test_config(self):
        '''testing the config method'''
        self.task.config(color='#000000')
        self.assertEqual(self.task.information['color'], '#000000')
        self.task.config(color=None)

    def test_hidden_config(self):
        '''testing the hidden_config method'''
        self.task.hidden_config(color='#000000')
        self.assertEqual(self.task.hidden_information['color'], '#000000')
        self.task.hidden_config(color=None)

    def test_cget(self):
        '''testing the cget method'''
        self.task.hidden_config(color=1234)
        expected_output = "Jun 28, 2017 15:18:38"
        self.assertEqual(self.task.cget('start_time'), expected_output)
        self.assertEqual(self.task.cget('color'), 1234)

class TestModelModel(unittest.TestCase):

    '''testing the Model class'''

    def setUp(self):
        '''setting up fixations'''
        os.chdir("/home/pcastr/toolsets/toolset/contrib/nightvision/unittests")
        self.database = model.Model()
        self.task = model.Task(start_time="Jun 28, 2017 15:18:38")
        self.task_id = self.task.information['task_id']
        self.database.addtask(self.task)
        if not os.path.exists("local_database"):
            os.makedirs("local_database")
        if not os.path.exists("dummy_dir"):
            os.makedirs("dummy_dir")
        if not os.path.exists("resources"):
            os.makedirs("resources")
        with open(LOG_SOURCES_FILE, 'w') as txtfile:
            txtfile.write("/projects/alegra/testing/logs/trigger.log")

    def tearDown(self):
        '''tearing down fixations'''
        os.chdir("/home/pcastr/toolsets/toolset/contrib/nightvision/unittests")
        del self.database
        del self.task
        shutil.rmtree("local_database")
        shutil.rmtree("dummy_dir")
        shutil.rmtree("resources")

    def test_removetask(self):
        '''testing the removetask method'''
        self.database.removetask(self.task_id)

    def test_addtask(self):
        '''testing the addtask method'''
        self.database.removetask(self.task_id)
        self.database.addtask(self.task)

    def test_getdatetasks_existing_date(self):
        '''testing the getdatetasks method, expecting a
        non-empty list as output'''
        date_to_check = datetime.datetime.strptime(
            "Jun 28, 2017 15:18:38",
            "%b %d, %Y %H:%M:%S")
        self.assertEqual(
            self.database.getdatetasks(date_to_check), [
                self.task_id])

    def test_getdatetasks_no_date(self):
        '''testing the getdatetasks method, expecting an
        empty list as output'''
        date_to_check = datetime.datetime.strptime(
            "Jun 29, 2017 15:18:38",
            "%b %d, %Y %H:%M:%S")
        self.assertEqual(
            self.database.getdatetasks(date_to_check), [])

    def test_hidden_config(self):
        '''testing the hidden_config method'''
        self.database.hidden_config(self.task_id, color='#000000')

    def test_config(self):
        '''testing the config method'''
        self.database.hidden_config(self.task_id, color="#000000")
        self.database.config(self.task_id, start_time="Jun 28, 2017 15:18:38")

    def test_cget(self):
        '''testing the cget method'''
        expected_output = "Jun 28, 2017 15:18:38"
        self.assertEqual(
            self.database.cget(
                self.task_id,
                'start_time'),
            expected_output)

    def test_get_all_children(self):
        '''testing the get_all_children method'''
        child1 = model.Task(
            parent=self.task_id,
            start_time="Jun 28, 2017 15:18:38")
        child1_id = child1.cget('task_id')
        child2 = model.Task(
            parent=child1_id,
            start_time="Jun 28, 2017 15:18:38")
        child2_id = child2.cget('task_id')
        child1.hidden_config(children=[child2_id])
        self.database.hidden_config(self.task_id, children=[child1_id])
        self.database.addtask(child1)
        self.database.addtask(child2)
        self.assertEqual(
            self.database.get_all_children(
                self.task_id), [
                    child1_id, child2_id])

    def test_get_task_depth(self):
        '''testing the task_depth method'''
        child = model.Task(
            start_time="Jun 28, 2017 15:18:38",
            parent=self.task_id)
        child_id = child.cget('task_id')
        self.database.addtask(child)
        self.database.hidden_config(self.task_id, children=[child_id])
        self.assertEqual(self.database.get_task_depth(child_id), 1)

    def test_dateexists_expecting_true(self):
        '''testing the dateexists method, expecting an output of True'''
        date_to_check = datetime.datetime.strptime(
            "Jun 28, 2017 15:18:38",
            "%b %d, %Y %H:%M:%S")
        self.assertTrue(self.database.dateexists(date_to_check))

    def test_dateexists_expecting_false(self):
        '''testing the dateexists method, expecting an output of False'''
        date_to_check = datetime.datetime.strptime(
            "Jun 29, 2017 15:18:38",
            "%b %d, %Y %H:%M:%S")
        self.assertFalse(self.database.dateexists(date_to_check))

    def test_getinfo(self):
        '''testing the getinfo method'''
        info = self.database.getinfo(self.task_id)
        expected_info = {'start_time': "Jun 28, 2017 15:18:38",
                         'task_id': self.task_id}
        self.assertEqual(info, expected_info)

    def test_gethiddeninfo(self):
        '''testing the gethiddeninfo method'''
        self.database.hidden_config(self.task_id, color='#000000')
        info = self.database.gethiddeninfo(self.task_id)
        expected_info = {'color': '#000000', 'parent': 'root', 'visible': True,
                         'since_epoch': 1498688318.0, 'children': []}
        self.assertEqual(info, expected_info)

    def test_update_nonexistent_file(self):
        '''testing the update method, without an existing file'''
        date_to_check = datetime.datetime.strptime(
            "Jul 03, 2017 15:18:38",
            "%b %d, %Y %H:%M:%S")
        self.database.update(date_to_check)
        new_file_path = os.path.join("local_database", "Jul_03_2017.json")
        self.assertTrue(os.path.exists(new_file_path))

    def test_update_existing_file(self):
        '''testing the update method, without an existing file'''
        date_to_check = datetime.datetime.strptime(
            "Jul 03, 2017 15:18:38",
            "%b %d, %Y %H:%M:%S")
        new_file_path = os.path.join("local_database", "Jul_03_2017.json")
        with open(new_file_path, 'w') as jsonfile:
            content = {"dummyID": [
                {"start_time": "Jul 03, 2017 15:18:38",
                 "x_buffer": 1234},
                {"color": 1234,
                 "parent": 1234}]}
            json.dump(content, jsonfile)
        self.database.update(date_to_check)
        self.assertTrue(os.path.exists(new_file_path))

    def test_save_database(self):
        '''testing the save_database method'''
        new_file_path = os.path.join("local_database", "Jun_28_2017.json")
        self.database.save_database()
        self.assertTrue(os.path.exists(new_file_path))

    def test_search_taskid_exact(self):
        '''testing the search method with arguments to cause an exact match'''
        expected_result = {self.task_id: None}
        result = self.database.search(
            'task_id', str(
                self.task_id), [
                    self.task_id])
        self.assertEqual(result, expected_result)

    def test_search_taskid_incomplete(self):
        '''testing the search method with the arguments to cause an imcomplete
        match'''
        expected_result = {self.task_id: None}
        result = self.database.search(
            'task_id', str(
                self.task_id)[0], [
                    self.task_id])
        self.assertEqual(result, expected_result)

    def test_search_starttime(self):
        '''testing the search method with the search term "start_time"'''
        expected_result = {self.task_id: self.task.cget('start_time')}
        result = self.database.search('start_time', ' ', [self.task_id])
        self.assertEqual(result, expected_result)

    def test_clean_period(self):
        '''testing the clean_period method'''
        first_date = datetime.datetime(2017, 6, 28, 15, 0, 0)
        last_date = datetime.datetime(2017, 6, 29, 15, 0, 0)
        self.database.clean_period(first_date, last_date)
        date_to_check = datetime.datetime.strptime(
            "Jun 28, 2017 15:18:38",
            "%b %d, %Y %H:%M:%S")
        self.assertEqual(self.database.getdatetasks(date_to_check), [])

    def test_load_task_with_child(self):
        '''testing the load_task method with a child task and with
        self.task as the parent'''
        date_to_check = datetime.datetime.strptime(
            "Jul 16, 2017 12:00:00",
            "%b %d, %Y %H:%M:%S")
        logfile = "/projects/alegra/testing/logs/\
job_gather.py_Sun_Jul_16_2017_19:59:40_MDT/log.txt"
        task_content = {
            "exit": "0",
            "finish": 1500256856.0,
            "logdate": 1500256853.617436,
            "logfile": logfile,
            "name": "job_gather.py",
            "start": 1500256780.0,
            "subjobs": [
                {
                    "exit": "0",
                    "finish": 1500220839.0,
                    "name": "job_gather.py",
                    "start": 1500220777.0,
                    "subjobs": []
                }]
        }
        self.database.load_task(task_content, self.task)
        self.assertEqual(len(self.database.getdatetasks(date_to_check)), 2)

    def test_load_task_without_end_time(self):
        '''testing the load_task method without an end time'''
        date_to_check = datetime.datetime.strptime(
            "Jul 16, 2017 12:00:00",
            "%b %d, %Y %H:%M:%S")
        task_content = {
            "name": "job_gather.py",
            "start": 1500256780.0,
            "subjobs": []
        }
        self.database.load_task(task_content, self.task)
        self.assertEqual(len(self.database.getdatetasks(date_to_check)), 1)

    def test_parseupdate(self):
        '''testing the parseupdate method. this needs
        to be updated when parseupdate is changed'''
        pwd = os.getcwd()
        newpwd = '/'.join(pwd.split('/')[:-1])
        os.chdir(newpwd)
        # os.makedirs("local_database")
        dates_to_check = [datetime.datetime.strptime("Apr 25, 2017 18:00:00",
                                                     "%b %d, %Y %H:%M:%S"),
                          datetime.datetime.strptime("Apr 26, 2017 18:00:00",
                                                     "%b %d, %Y %H:%M:%S")]
        self.database.parseupdate(
            dates_to_check[0],
            dates_to_check[1])
        self.assertEqual(len(self.database.getdatetasks(dates_to_check[0])), 2)

if __name__ == '__main__':
    unittest.main()
