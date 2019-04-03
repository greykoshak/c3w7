from __future__ import absolute_import, unicode_literals

import json
from smtplib import SMTPException

import requests
from celery import task
from django.core.mail import send_mail
from django.http import HttpResponse

from django.conf import settings  # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
from requests import RequestException, HTTPError

from .models import Setting


@task()
def smart_home_manager():
    current_state = CleverSystem.get_controller_state()
    new_states = {}

    # 1. Утечка воды
    if current_state['leak_detector']:
        if current_state['cold_water']:
            new_states['cold_water'] = False  # Close cold water
        if current_state['hot_water']:
            new_states['hot_water'] = False  # Close hot water
        AlertMail.send_alert()

    # 2. Нет холодной воды
    if not current_state['cold_water']:
        if current_state['boiler']:
            new_states['boiler'] = False  # Switch off boiler
        if current_state['washing_machine'] == 'on':
            new_states['washing_machine'] = "off"  # Switch off boiler

    # 3. Температура горячей воды (бойлер)
    hot_water_target_temperature = AccessBD.get_value_DB("hot_water_target_temperature", 80)

    if current_state['cold_water'] and (current_state['boiler_temperature'] <= int(hot_water_target_temperature * 0.9)) and \
            not current_state['boiler'] and not current_state['leak_detector']:
        new_states['boiler'] = True
    elif current_state['boiler'] and \
            (not current_state['cold_water'] or current_state['cold_water'] and
             current_state['boiler_temperature'] > int(hot_water_target_temperature * 1.1)):
        new_states['boiler'] = False

    # 5. Управлением шторами
    if current_state['curtains'] != 'slightly_open':
        if current_state['outdoor_light'] < 50 and not current_state['bedroom_light'] and \
                current_state['curtains'] == 'close':
            new_states['curtains'] = "open"  # Open curtains
        elif (current_state['outdoor_light'] > 50 or current_state['bedroom_light']) and \
                current_state['curtains'] == 'open':
            new_states['curtains'] = "close"  # Close curtains

    # 6. Задымление
    if current_state['smoke_detector']:
        if current_state['air_conditioner']:
            new_states['air_conditioner'] = False  # Switch off air_conditioner
        if current_state['bedroom_light']:
            new_states['bedroom_light'] = False  # Switch off bedroom_light
        if current_state['bathroom_light']:
            new_states['bathroom_light'] = False  # Switch off bathroom_light
        if current_state['boiler']:
            new_states['boiler'] = False  # Switch off boiler
        if current_state['washing_machine'] == 'on':
            new_states['washing_machine'] = "off"  # Switch off washing_machine

    # 7. Температура в спальне (air_conditioner)
    bedroom_target_temperature = AccessBD.get_value_DB("bedroom_target_temperature", 21)

    if (current_state['bedroom_temperature'] > int(bedroom_target_temperature * 1.1)) and \
            not current_state['air_conditioner']:
        new_states['air_conditioner'] = True
    elif current_state['bedroom_temperature'] < int(bedroom_target_temperature * 0.9) and \
            not current_state['air_conditioner']:
        new_states['air_conditioner'] = False

    if new_states:
        change_state = CleverSystem.create_states(new_states)
        CleverSystem.put_controller_state(change_state)

    return


class CleverSystem():
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

class AccessBD():
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


class AlertMail():
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
