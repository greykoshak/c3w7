from __future__ import absolute_import, unicode_literals

import json
from smtplib import SMTPException

import requests
from celery import task
from django.conf import settings  # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
from django.core.mail import send_mail
from django.http import HttpResponse
from requests import RequestException, HTTPError

from .models import Setting


@task()
def smart_home_manager():
    current_state = CleverSystem.get_controller_state()
    new_states = {}

    if not ControlCmd.is_leak_detector(current_state, new_states):
        # 2. Нет холодной воды
        ControlCmd.is_cold_water_detector(current_state, new_states)

    if not ControlCmd.is_smoke_detector(current_state, new_states):
        # 3. Управление бойлером
        ControlCmd.is_needed_hot_water(current_state, new_states)

        # 7. Температура в спальне (air_conditioner)
        ControlCmd.is_needed_change_temperature(current_state, new_states)

    # 5. Управлением шторами
    ControlCmd.is_curtains_slightly_open(current_state, new_states)

    if new_states:
        change_state = CleverSystem.create_states(new_states)
        CleverSystem.put_controller_state(change_state)

    return


# -------------------------------------- Defines classes -----------------------------------------
class CleverSystem:
    HEADERS = {
        'Authorization': 'Bearer {}'.format(settings.SMART_HOME_ACCESS_TOKEN)
    }
    API_URL = settings.SMART_HOME_API_URL
    ret_get_code = 0
    ret_post_code = 0

    # Get states of all controllers
    @classmethod
    def get_controller_state(cls):
        controller_data = dict()
        try:
            response = requests.get(cls.API_URL, headers=cls.HEADERS)
            cls.ret_get_code = response.status_code
            response.raise_for_status()
            r = response.json()

            if r['status'] == 'ok':
                data = r['data']

                for rec in data:
                    # print(f"{rec['name']}: {rec['value']}")
                    controller_data[rec['name']] = rec['value']
            else:
                return HttpResponse(status=502)
        except (RequestException, KeyError, ValueError):
            return HttpResponse(status=502)
        return controller_data

    # Создать управляющую структуру для умного дома, понятной API
    @staticmethod
    def create_states(dict_states: dict) -> dict:
        change_state = {}

        if dict_states:
            change_state["controllers"] = list()
            for key, value in dict_states.items():
                change_state['controllers'].append({"name": key, "value": value})
        return change_state

    # Record new states of controllers
    @classmethod
    def put_controller_state(cls, payload_dict: dict):
        try:
            r = requests.post(cls.API_URL, headers=cls.HEADERS,
                              data=json.dumps(payload_dict))
            cls.ret_post_code = r.status_code
            r.raise_for_status()
        except (RequestException, KeyError, ValueError, HTTPError):
            return HttpResponse(status=502)
        return r.status_code


# ------------------------------ EOClass CleverSystem() ----------------------------------

class ControlCmd:
    @staticmethod
    def is_leak_detector(states: dict, change: dict):
        # 1. Утечка воды
        if states['leak_detector']:
            if states['cold_water']:
                change['cold_water'] = False  # Close cold water
                if states['boiler']:
                    change['boiler'] = False  # Switch off boiler
                if states['washing_machine'] == 'on':
                    change['washing_machine'] = "off"  # Switch off boiler
            if states['hot_water']:
                change['hot_water'] = False  # Close hot water
            AlertMail.send_alert()
            return True
        return False

    @staticmethod
    def is_cold_water_detector(states: dict, change: dict):
        # 2. Нет холодной воды
        if not states['cold_water']:
            if states['boiler']:
                change['boiler'] = False  # Switch off boiler
            if states['washing_machine'] == 'on':
                change['washing_machine'] = "off"  # Switch off boiler

    @staticmethod
    def is_needed_hot_water(states: dict, change: dict):
        # 3. Управление бойлером
        hot_water_target_temperature = AccessBD.get_value_DB("hot_water_target_temperature", 80)

        if not states['boiler'] and states['cold_water'] and not states['leak_detector'] and \
                (states['boiler_temperature'] < int(hot_water_target_temperature * 0.9)):
            change['boiler'] = True
        elif states['boiler'] and \
                states['boiler_temperature'] > int(hot_water_target_temperature * 1.1):
            change['boiler'] = False

    @staticmethod
    def is_curtains_slightly_open(states: dict, change: dict):
        # 5. Управлением шторами
        if states['curtains'] != 'slightly_open':
            if states['curtains'] == 'close' and \
                    (states['outdoor_light'] < 50 and not states['bedroom_light']):
                change['curtains'] = "open"  # Open curtains
            elif states['curtains'] == 'open' and \
                    (states['outdoor_light'] > 50 or states['bedroom_light']):
                change['curtains'] = "close"  # Close curtains

    @staticmethod
    def is_smoke_detector(states: dict, change: dict):
        # 6. Задымление
        if states['smoke_detector']:
            if states['air_conditioner']:
                change['air_conditioner'] = False  # Switch off air_conditioner
            if states['bedroom_light']:
                change['bedroom_light'] = False  # Switch off bedroom_light
            if states['bathroom_light']:
                change['bathroom_light'] = False  # Switch off bathroom_light
            if states['boiler']:
                change['boiler'] = False  # Switch off boiler
            if states['washing_machine'] == 'on':
                change['washing_machine'] = "off"  # Switch off washing_machine
            return True
        return False

    @staticmethod
    def is_needed_change_temperature(states: dict, change: dict):
        # 7. Температура в спальне (air_conditioner)
        bedroom_target_temperature = AccessBD.get_value_DB("bedroom_target_temperature", 21)

        if not states['air_conditioner'] and \
                (states['bedroom_temperature'] > int(bedroom_target_temperature * 1.1)):
            change['air_conditioner'] = True
        elif states['air_conditioner'] and \
                states['bedroom_temperature'] < int(bedroom_target_temperature * 0.9):
            change['air_conditioner'] = False


# ------------------------------ EOClass ControlCmd() ----------------------------------

class AccessBD:
    # Get value from DB
    @staticmethod
    def get_value_DB(controller_name: str, default_value: int) -> int:
        try:
            obj = Setting.objects.get(controller_name=controller_name)
        except Setting.DoesNotExist:
            obj = Setting(controller_name=controller_name, value=default_value)
            obj.save()
        return obj.value

    @staticmethod
    def set_value_DB(controller_name: str, current_value: int):
        try:
            obj = Setting.objects.get(controller_name=controller_name)
            obj.value = current_value
            obj.save()
        except Setting.DoesNotExist:
            return HttpResponse(status=502)
        return obj.value


# ------------------------------ EOClass AccessBD() ----------------------------------

class AlertMail:
    message = "Leak!"
    USER_FROM = settings.EMAIL_HOST_USER
    USER_TO = settings.EMAIL_RECEPIENT

    @classmethod
    def send_alert(cls):
        try:
            send_mail('Alert', cls.message, cls.USER_FROM, [cls.USER_TO],
                      fail_silently=False)
        except SMTPException:
            pass

# ------------------------------ EOClass AlertMail() ----------------------------------
