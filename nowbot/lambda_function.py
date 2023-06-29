import boto3
import copy
import json
import operator
import os
import re
import urllib3
import yaml
from datetime import datetime, timedelta, timezone
import dynamodb_json as ddbjson

def lambda_handler(event, context):

    # CONFIGURE NEW PASTE
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    entry = datetime.now().strftime('mihobu-now-summary-%Y%m%d-%H%M%S')

    # OMG.LOL API CONFIG
    omg_now_url = 'https://api.omg.lol/address/mihobu/now'
    omg_paste_url = f'https://api.omg.lol/address/mihobu/weblog/entry/{entry}'
    omg_api_key = os.environ['OMG_API_KEY']
    omg_headers = { 'Authorization': f'Bearer {omg_api_key}' }
    
    # GET DYNAMODB CLIENT
    ddb_client = boto3.client('dynamodb')
    
    # GET LAST WEEK'S DATES
    oneweekago = datetime.now() - timedelta(days=7) # must be 7 for "last week"
    weeknum = int(oneweekago.strftime('%U'))
    year = int(oneweekago.strftime('%Y'))
    dt_from = datetime.fromisocalendar(year, weeknum, 1).strftime('%Y%m%d-000000')
    dt_to = datetime.fromisocalendar(year, weeknum, 7).strftime('%Y%m%d-235959')
    print(dt_from, "thru", dt_to)
    
    # GET LAST WEEK'S ITEMS FROM DYNAMODB
    data = []
    resp = ddb_client.scan(
        TableName='now-content-v7',
        Select='ALL_ATTRIBUTES',
        ExpressionAttributeNames={'#MODIFIED': 'modified'},
        ExpressionAttributeValues={':FROM': {'S': dt_from},':TO': {'S': dt_to}},
        FilterExpression='#MODIFIED BETWEEN :FROM AND :TO'
    )
    data = data + resp['Items']
    content = sorted(ddbjson.loads(data), key=lambda x: x['modified'], reverse=True)

    # CONSTRUCT THE PASTE CONTENT
    outputstr = f'''
---
Date: {ts}
Template: Main Template
Status: draft
---

# Now Page Summary for Week {weeknum} ({ts})

'''

    italpat = re.compile("^(.*)\*([^\*]+)\*(.*)$") # for converting italics markdown
    outputstr += '<ul class="fa-ul">'
    for item in content:
        if 'icon' in item.keys():
            the_icon = item['icon']
        else:
            the_icon += "otter"
        outputstr += f'''<li><span class="fa-li"><i class="fa-solid fa-{the_icon}"></i></span>'''
        if 'url' in now_item.keys():
            outputstr += f'''<a href="{item['url']}">{item['title']}</a>'''
        else:
            outputstr += item['title']
        if 'last-episode' in item.keys():
            outputstr += f''' (Ep. {item['last-episode']})'''
        if 'progress' in item.keys():
            pr = item['progress']
            mod_date = datetime.strptime(item['modified'], '%Y%m%d-%H%M%S')
            ttts = mod_date.strftime('%Y-%m-%d')
            outputstr += f''' <div class="progress-bar-container" style="--pct:{pr}%;" data-tooltip="{pr}% on {ttts}"></div>'''
        if 'rating' in item.keys():
            rt = int(item['rating'])
            outputstr += ' <div class="ratings-container"><span class="star-on">'
            outputstr += '★' * rt
            outputstr += '</span><span class="star-off">'
            outputstr += '★' * (5-rt)
            outputstr += '</span></div>'
        outputstr += "</li>\n"
    outputstr += '</ul>'

    # GET A CONNECTION POOL
    http = urllib3.PoolManager()
    
    # CREATE THE WEBLOG ENTRY
    entry = {
        "entry": entry,
        "body": outputstr
    }
    resp3 = http.request('POST', omg_paste_url, body=outputstr.encode('utf-8'), headers=omg_headers)
    print(resp3.status)
