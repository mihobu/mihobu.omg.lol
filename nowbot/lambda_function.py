# =====================================================================
# NOWBOT - PULL RECORDS FROM DYNAMODB AND BUILD NOW PAGE CONTENT
# =====================================================================

import boto3
import dynamodb_json as ddbjson
import json
import urllib3

from copy import deepcopy
from datetime import datetime, timedelta

# =====================================================================
# RETURN ALL DICTS IN A GIVE LIST, IF k==v.
# RETURN None OTHERWISE.
# =====================================================================
def filter_by_type(items, itemtype):
    r = []
    for item in items:
        if item['type'] == itemtype:
            r.append(item)
    return r

# =====================================================================
# RETURN THE VALUE FROM A DICT IN A GIVEN LIST IF THE NAME MATCHES
# =====================================================================
def get_value_from(test_list, name):
    return next((item['Value'] for item in test_list if item['Name'] == name), None)

# =====================================================================
# LAMBDA HANDLER FUNCTION
# =====================================================================
def lambda_handler(event, context):

    #--
    #-- GET PARAMETERS FROM PARAMETER STORE
    #--
    ssm_client = boto3.client('ssm')
    parameters = [
      'OMG_API_KEY',
      'TRAKT_HISTORY_INTERVAL'
    ]
    resp_ssm = ssm_client.get_parameters(Names=parameters)
    omg_api_key = get_value_from(resp_ssm['Parameters'], 'OMG_API_KEY')
    display_days = int(get_value_from(resp_ssm['Parameters'], 'TRAKT_HISTORY_INTERVAL'))

    #--
    #-- CONFIGURATION
    #--
    
    # GENERAL CONFIGURATION
    content_version = '7'
    type_names = {
        "L": "Listening",
        "R": "Reading",
        "W": "Watching",
        "T": "Tinkering"
    }
    global req_attrs
    req_attrs = ['title', 'type']
    global opt_attrs 
    opt_attrs = ['id', 'icon', 'url', 'progress', 'last-episode', 'delete', 'rating', 'note', 'trakt_id']
    
    # DYNAMO DB CONFIG
    table_name = f"now-content-v{content_version}"
    
    # OMG.LOL CONFIG
    omg_now_url = 'https://api.omg.lol/address/mihobu/now'
    omg_headers = { 'Authorization': f'Bearer {omg_api_key}' }
    
    # GET A CONNECTION POOL
    http = urllib3.PoolManager()
    
    # GET DYNAMODB CLIENT
    ddb_client = boto3.client('dynamodb')
    ddb_resource = boto3.resource('dynamodb')
    ddb_table = ddb_resource.Table(table_name)

    #--
    #-- GET "RECENT" ITEMS FROM DYNAMODB
    #--
    start_at = datetime.now() - timedelta(days=display_days)
    start_at_str = start_at.strftime('%Y%m%d-000000')
    resp = ddb_table.scan(
        TableName=table_name,
        Select='ALL_ATTRIBUTES',
        ExpressionAttributeNames={"#modified": "modified"},
        ExpressionAttributeValues={':STARTAT': start_at_str},
        FilterExpression="#modified >= :STARTAT"
    )
    recent_items_d = resp['Items']
    recent_items = ddbjson.loads(recent_items_d)
    print("* Loaded {} recent items from DynamoDB".format(len(recent_items)))

    #--
    #-- CONSTRUCT AND UPDATE THE NOW PAGE CONTENT
    #--
    print("* Writing NOW content")
    now = '''
{profile-picture}
    
# Michael Burkhardt

## What I’m Doing Now

This is what I’ve been into lately.

I also post a [weekly summary](https://blog.mihobu.lol/tag/weeknotes).

<script src="https://status.lol/mihobu.js?time&fluent&pretty&link"></script>

'''

    # GET RECENT ITEMS IN EACH CATEGORY
    for typ in ["R", "W", "L", "T"]: # In display order
        type_icon = '<img src="https://cdn.some.pics/mihobu/64b09a5b33bac.png" class="emoji">' if typ == "W" else ''
        now += f"\n### {type_names[typ]} {type_icon}\n\n"
        now_items = sorted(filter_by_type(recent_items, typ), key=lambda x: x['modified'], reverse=True)
        if len(now_items) == 0:
            now += "- No recent items to show {otter}\n"
        else:
            for now_item in now_items:
                
                if 'url' in now_item.keys():
                    now += f"- [{now_item['title']}]({now_item['url']})"
                else:
                    now += f"- {now_item['title']}"
                if 'last-episode' in now_item.keys():
                    now += f" (Ep. {now_item['last-episode']})"
                if 'progress' in now_item.keys():
                    pr = now_item['progress']
                    mod_date = datetime.strptime(now_item['modified'], '%Y%m%d-%H%M%S')
                    ttts = mod_date.strftime('%Y-%m-%d')
                    now += f' <div class="progress-bar-container" style="--pct:{pr}%;" data-tooltip="{pr}% on {ttts}"></div>'
                if 'rating' in now_item.keys():
                    rt = float(now_item['rating'])
                    num_full_stars = str(int(rt))
                    num_half_stars = "1" if (rt-int(rt)) > 0 else "0"
                    now += f'<div class="star-rating" style="--f:{num_full_stars};--h:{num_half_stars}"></div>'
                if 'icon' in now_item.keys():
                    now += f" {{{now_item['icon']}}}\n"
                else:
                    now += f" {{otter}}\n"

    now += '''

<div class="nowlol"><a href="https://hello.mihobu.lol/">HELLO</a> ⎮ <span>NOW</span> ⎮ <a href="https://blog.mihobu.lol/">BLOG</a></div>

{last-updated}

<div style="display:none"><a rel="me" href="https://social.lol/@mihobu">Mastodon</a></div>

<img id="dont-touch-image" src="https://mihobu.url.lol/profile-note" />

<script src="https://tinylytics.app/embed/3uCnpsxr9keeKJvKdRxF.js" defer></script>
'''

    # CALL THE OMG.LOL API TO UPDATE THE NOW PAGE CONTENTS
    payload_now = {
        'content': now,
        'listed': 1
    }
    resp_now = http.request('POST', omg_now_url, body=json.dumps(payload_now), headers=omg_headers)
    
    print("* Done!")
