from __future__ import absolute_import, unicode_literals

import json
from smtplib import SMTPException

import requests
from celery import task
from django.core.mail import send_mail
from django.http import HttpResponse

from coursera_house.settings import SMART_HOME_ACCESS_TOKEN, SMART_HOME_API_URL, EMAIL_HOST_USER, EMAIL_RECEPIENT
from .models import Setting

HEADERS = {
    'Authorization': 'Bearer ' + SMART_HOME_ACCESS_TOKEN
}


@task()
def smart_home_manager():
    current_state = get_controller_state()
    new_states = {}

    # 1. Утечка воды
    if current_state['leak_detector']:
        if current_state['cold_water']:
            new_states['cold_water'] = "false"  # Close cold water
        if current_state['hot_water']:
            new_states['hot_water'] = "false"  # Close hot water
        send_alert("Leak!")

    # 2. Нет холодной воды
    if not current_state['cold_water']:
        if current_state['boiler']:
            new_states['boiler'] = "false"  # Switch off boiler
        if current_state['washing_machine'] == 'on':
            new_states['washing_machine'] = "off"  # Switch off boiler

    # 3. Температура горячей воды (бойлер)
    hot_water_target_temperature = get_value("hot_water_target_temperature", None, 80)

    if (current_state['boiler_temperature'] <= hot_water_target_temperature * 0.9) and \
            not current_state['boiler'] and not current_state['leak_detector']:
        new_states['boiler'] = "true"
    elif (current_state['boiler_temperature'] > hot_water_target_temperature * 1.1) and current_state['boiler']:
        new_states['boiler'] = "false"

    # 5. Управлением шторами
    if current_state['outdoor_light'] <= 50 and not current_state['bedroom_light'] and \
                    current_state['curtains'] == 'close':
        new_states['curtains'] = "open"  # Open curtains
    elif (current_state['outdoor_light'] > 50 or current_state['bedroom_light']) and \
                    current_state['curtains'] == 'open':
        new_states['curtains'] = "close"  # Close curtains

    # 6. Задымление
    if current_state['smoke_detector']:
        if current_state['air_conditioner']:
            new_states['air_conditioner'] = "false"  # Switch off air_conditioner
        if current_state['bedroom_light']:
            new_states['bedroom_light'] = "false"  # Switch off bedroom_light
        if current_state['bathroom_light']:
            new_states['bathroom_light'] = "false"  # Switch off bathroom_light
        if current_state['boiler']:
            new_states['boiler'] = "false"  # Switch off boiler
        if current_state['washing_machine'] == 'on':
            new_states['washing_machine'] = "off"  # Switch off washing_machine

    # 7. Температура в спальне (air_conditioner)
    bedroom_target_temperature = get_value("bedroom_target_temperature", None, 21)

    if (current_state['bedroom_temperature'] > bedroom_target_temperature * 1.1) and \
            not current_state['air_conditioner']:
        new_states['air_conditioner'] = "true"
    elif (current_state['bedroom_temperature'] <= bedroom_target_temperature * 0.9) and \
            not current_state['air_conditioner']:
        new_states['air_conditioner'] = "false"

    if new_states:
        change_state = create_states(new_states)
        put_controller_state(change_state)

    return


# Создать управляющую структуру для умного дома
def create_states(dict_states: dict) -> dict:
    change_state = {}

    if dict_states:
        change_state["controllers"] = list()
        # change_state["controllers"] = [change_state['controllers']
        #                                    .append({"name": key, "value": value}) for key, value in dict_states.items()]
        for key, value in dict_states.items():
            change_state['controllers'].append({"name": key, "value": value})

    return change_state


# Get states of all controllers
def get_controller_state():
    controller_data = dict()

    try:
        response = requests.get(SMART_HOME_API_URL, headers=HEADERS)
        response.raise_for_status()
        r = response.json()

        if r['status'] == 'ok':
            data = r['data']

            for rec in data:
                print(f"{rec['name']}: {rec['value']}")
                controller_data[rec['name']] = rec['value']
        else:
            return HttpResponse(status=502)
    except requests.exceptions.HTTPError as err_http:
        print("HTTP error:", err_http)
    return controller_data


# Record new states of controllers
def put_controller_state(payload_dict: dict):
    try:
        r = requests.post(SMART_HOME_API_URL, headers=HEADERS, data=json.dumps(payload_dict))
        r.raise_for_status()

    except requests.exceptions.HTTPError as err_http:
        print("HTTP error:", err_http)
    return


def get_value(controller_name: str, current_value, default_value: int) -> int:
    try:
        obj = Setting.objects.get(controller_name=controller_name)
        if current_value is not None and obj.value != current_value:
            obj.update(value=current_value)
    except Setting.DoesNotExist:
        obj = Setting(controller_name=controller_name, value=default_value)
        obj.save()
    return obj.value


def send_alert(message):
    try:
        send_mail(
            'Alert',
            message,
            EMAIL_HOST_USER,
            [EMAIL_RECEPIENT],
            fail_silently=False,
        )
    except SMTPException:
        pass

# payload = {
#     "controllers": [
#         {
#             "name": "air_conditioner",
#             "value": "false"
#         },
#         {
#             "name": "bedroom_light",
#             "value": "false"
#         },
#         {
#             "name": "bathroom_motion",
#             "value": "false"
#         },
#
#     ]
# }
