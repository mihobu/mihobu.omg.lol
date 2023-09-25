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
        "B": "Books",
        "L": "Listening",
        "R": "Other Reading",
        "W": "Watching",
        "T": "Tinkering"
    }
    rating_word = {
        0.5: "Abysmal", 
        1.0: "Terrible",
        1.5: "Bad",
        2.0: "Poor",
        2.5: "Mediocre",
        3.0: "Good",
        3.5: "Quite Good",
        4.0: "Very Good",
        4.5: "Brilliant",
        5.0: "Great"
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
    nowts = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    now = f"""

This is what I’ve been into lately. I also post a [weekly summary](/tag/weeknotes).

<script src="https://status.lol/mihobu.js?time&fluent&pretty&link"></script>

"""

    # GET RECENT ITEMS IN EACH CATEGORY
    for typ in ["B", "R", "W", "L", "T"]: # In display order

        if typ == "W":
            type_icon = '<img src="https://cdn.some.pics/mihobu/64b09a5b33bac.png" class="emoji">'
        elif typ == "B":
            type_icon = '<img src="https://cdn.some.pics/mihobu/64e7a5eb061be.png" class="emoji">'
        else:
            type_icon = ''

        now += f"\n### {type_names[typ]} {type_icon}\n\n"
        #now += '<ul class="fa-ul">\n'
        now_items = sorted(filter_by_type(recent_items, typ), key=lambda x: x['modified'], reverse=True)
        if len(now_items) == 0:
            #now += f'''<li><span class="fa-li"><i class="fa-solid fa-otter"></i></span> No recent items to show</li>\n'''
            now += "- No recent items to show {otter}\n"
        else:
            for now_item in now_items:
                #now += f'''<li><span class="fa-li"><i class="fa-solid fa-{now_item['icon']}"></i></span>'''
                
                if 'url' in now_item.keys():
                    #now += f'''<a href="{now_item['url']}">{now_item['title']}</a>'''
                    now += f"- [{now_item['title']}]({now_item['url']})"
                else:
                    #now += f'''{now_item['title']}'''
                    now += f"- {now_item['title']}"
                    
                if 'last-episode' in now_item.keys():
                    now += f" (Ep. {now_item['last-episode']})"
                    
                if 'rating' in now_item.keys():
                    rt = float(now_item['rating'])
                    num_full_stars = str(int(rt))
                    num_half_stars = "1" if (rt-int(rt)) > 0 else "0"
                    now += f""" <div class="star-rating" style="--f:{num_full_stars};--h:{num_half_stars}" data-tooltip="{rating_word[rt]}" onclick="window.location.href='https://mihobu.lol/my-content-rating-system'"></div>"""
                elif 'progress' in now_item.keys():
                    # This is in an ELIF because I don't want both rating and progress to be shown.
                    # I'm assuming if there's a rating, then I've finished the item.
                    pr = now_item['progress']
                    if int(pr) == 100:
                        now += ' <img src="https://cdn.some.pics/mihobu/64d37c078bdb0.png" class="emoji">'
                    elif int(pr) > 0:
                        mod_date = datetime.strptime(now_item['modified'], '%Y%m%d-%H%M%S')
                        ttts = mod_date.strftime('%Y-%m-%d')
                        now += f' <div class="progress-bar-container" style="--pct:{pr}%;" data-tooltip="{pr}% on {ttts}"></div>'

                if 'icon' in now_item.keys():
                    now += f" {{{now_item['icon']}}}\n"
                else:
                    now += f" {{otter}}\n"

                #now += "</li>\n"
        #now += '</ul>\n'

    now += '''

<div style="display:none"><a rel="me" href="https://social.lol/@mihobu">Mastodon</a></div>
'''

    # CALL THE OMG.LOL API TO UPDATE THE NOW PAGE CONTENTS
    payload_now = {
        'content': now,
        'listed': 1
    }
    resp_now = http.request('POST', omg_now_url, body=json.dumps(payload_now), headers=omg_headers)
    
    print("* Done!")
