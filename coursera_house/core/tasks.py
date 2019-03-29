from __future__ import absolute_import, unicode_literals
from celery import task

import requests
import json

# from .models import Setting
from coursera_house.settings import SMART_HOME_ACCESS_TOKEN, SMART_HOME_API_URL

@task()
def smart_home_manager():
    # Здесь ваш код для проверки условий
    pass




headers = {
    'Authorization': 'Bearer ' + SMART_HOME_ACCESS_TOKEN
}
response = requests.get(SMART_HOME_API_URL, headers=headers).json()

if response['status'] == 'ok':
    data = response['data']

    for rec in data:
        print(f"{rec['name']}: {rec['value']}")
else:
    print("not ok")






payload = {
    "controllers": [
        {
            "name": "air_conditioner",
            "value": "true"
    },
    {
            "name": "bedroom_light",
            "value": "true"
    }
  ]
}

requests.post(SMART_HOME_API_URL, headers=headers, data=payload)



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