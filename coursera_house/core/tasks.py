from __future__ import absolute_import, unicode_literals

from django.core.mail import send_mail
from smtplib import SMTPException

import json

import requests
from celery import task

# from .models import Setting
from coursera_house.settings import SMART_HOME_ACCESS_TOKEN, SMART_HOME_API_URL, EMAIL_HOST_USER, EMAIL_RECEPIENT

HEADERS = {
    'Authorization': 'Bearer ' + SMART_HOME_ACCESS_TOKEN
}


@task()
def smart_home_manager():
    # Здесь ваш код для проверки условий
    pass


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
            raise requests.RequestException

    except requests.exceptions.HTTPError as err_http:
        print("HTTP error:", err_http)
    return controller_data


# Record new states of controllers
def put_controller_state(payload_dict):
    try:
        r = requests.post(SMART_HOME_API_URL, headers=HEADERS, data=json.dumps(payload_dict))
        r.raise_for_status()

    except requests.exceptions.HTTPError as err_http:
        print("HTTP error:", err_http)
    return


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
#
# put_controller_state(payload)

# url='http://www.google.com/blahblah'
#
# try:
#     r = requests.get(url,timeout=3)
#     r.raise_for_status()
# except requests.exceptions.HTTPError as errh:
#     print ("Http Error:",errh)
# except requests.exceptions.ConnectionError as errc:
#     print ("Error Connecting:",errc)
# except requests.exceptions.Timeout as errt:
#     print ("Timeout Error:",errt)
# except requests.exceptions.RequestException as err:
#     print ("OOps: Something Else",err)
#
# Http Error: 404 Client Error: Not Found for url: http://www.google.com/blahblah

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