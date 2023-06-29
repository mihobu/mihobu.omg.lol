import boto3
import dynamodb_json as ddbjson
import json
import os
import urllib3
import yaml
from datetime import datetime, timedelta

def find_title(test_list, title):
    idx = None
    for x in range(len(test_list)):
        tt = test_list[x]['title']
        if tt == title:
            idx = x
            break
    return idx

def validate_input_item(input_item):
    req_attrs = ['title', 'type']
    opt_attrs = ['created', 'modified', 'icon', 'url', 'progress', 'last-episode']
    all_attrs = req_attrs + opt_attrs
    is_valid = True
    # check required attribtues
    for ra in req_attrs:
        if ra not in input_item.keys():
            print(f"Required attribute ({ra}) not found in input item")
            is_valid = False
    # check all attributes
    for k in input_item.keys():
        if k not in all_attrs:
            print(f"Invalid attribute ({k}) found in input item")
            is_valid = False
    return is_valid

def filter_by_type(items, itemtype):
    r = []
    for item in items:
        if item['type'] == itemtype:
            r.append(item)
    return r

def lambda_handler(event, context):

    # GENERAL CONFIGURATION
    display_days = 7
    content_version = '6a'
    type_names = {
        "L": "Listening",
        "R": "Reading",
        "W": "Watching",
        "T": "Tinkering"
    }
    
    # DYNAMO DB CONFIG
    table_name = f"now-content-v{content_version}"
    
    # OMG.LOL CONFIG
    omg_now_url = 'https://api.omg.lol/address/mihobu/now'
    omg_paste_url = 'https://api.omg.lol/address/mihobu/pastebin'
    omg_api_key = '53d851d9ea975216b986af12ffc4a875'
    omg_headers = { 'Authorization': f'Bearer {omg_api_key}' }
    yaml_url = f"https://mihobu.paste.lol/media{content_version}.yaml/raw"

    # FORCE UPDATE?
    force = True if (('force-update' in event.keys()) and (event['force-update']=="true")) else False

    # GET A CONNECTION POOL
    http = urllib3.PoolManager()

    # GET DYNAMODB CLIENT
    ddb_client = boto3.client('dynamodb')
    ddb_resource = boto3.resource('dynamodb')
    ddb_table = ddb_resource.Table(table_name)

    # =====================================================================
    # LOAD THE USER'S YAML FILE FROM PASTEBIN
    # =====================================================================
    resp = http.request('GET', yaml_url)
    input_items = yaml.load(resp.data, Loader=yaml.loader.BaseLoader) # force all to string
    if input_items is None:
        # YAML content is empty, so create empty list
        input_items = []
    print("* Loaded {} input items from pastebin".format(len(input_items)))
    
    # =====================================================================
    # GET "RECENT" ITEMS FROM DYNAMODB
    # =====================================================================
    oneweekago = datetime.now() - timedelta(days=display_days)
    owa_str = oneweekago.strftime('%Y-%m-%d-00-00-00')
    resp = ddb_table.scan(
        TableName=table_name,
        Select='ALL_ATTRIBUTES',
        ExpressionAttributeNames={"#modified": "modified"},
        ExpressionAttributeValues={':ONEWEEKAGO': owa_str},
        FilterExpression="#modified >= :ONEWEEKAGO"
    )
    recent_items_d = resp['Items']
    recent_items = ddbjson.loads(recent_items_d)
    print("* Loaded {} recent items from DynamoDB".format(len(recent_items)))

    # CREATE A LIST FOR INVALID ITEMS
    invalid_items = []
    
    # LISTS OF TITLES TO ADD/UPDATE IN DYNAMODB
    update_titles = []
    new_titles = []

    # =====================================================================
    # COMPARE INPUT ITEMS TO RECENT ITEMS
    # =====================================================================
    for input_item in input_items:
        
        title = input_item['title']
        
        # Validate the item
        if not validate_input_item(input_item):
            invalid_items.append(input_item)
            continue
      
        # Does input_item exist in recent items?
        recent_item_idx = find_title(recent_items, title)
    
        # Case 1: item is new
        if recent_item_idx is None:
            print(f"* Adding new item: {title}")
            ts = datetime.now().strftime('%Y%m%d-%H%M%S')
            input_item['modified'] = ts
            input_item['created'] = ts
            recent_items.append(input_item)
            new_titles.append(title)
            continue
        
        # Case 2: input item title matches an existing recent item
        #         AND at least one data attribute has changed (item has been modified)
        recent_item = recent_items[recent_item_idx]
        upd = False
        for k in input_item.keys():
            if k in ['modified', 'created']:
                # ignore timestamp attributes
                continue
            if (k not in recent_item) or (recent_item[k] != input_item[k]):
                print(f"* Adding or updating attribute ({k}) to {title}")
                upd = True
                recent_item[k] = str(input_item[k])
                recent_item['modified'] = datetime.now().strftime('%Y%m%d-%H%M%S')
        
        if upd:
            update_titles.append(title) # only do once!

    # =====================================================================
    # INSERT NEW ITEMS IN DYNAMODB
    # =====================================================================
    if len(new_titles) > 0:
        for title in new_titles:
            print(f"* Adding new item: {title}")
            idx = find_title(recent_items, title)
            item = recent_items[idx]
            item_d = ddbjson.dumps(item, as_dict=True)
            ddb_client.put_item(
                TableName=table_name,
                Item=item_d
            )
    else:
        print("* No new items to create")

    # =====================================================================
    # UPDATE ITEMS IN DYNAMODB
    # =====================================================================
    if len(update_titles) > 0:
        for title in update_titles:
            idx = find_title(recent_items, title)
            cre = recent_items[idx]['created']
    
            # DELETE THE ITEM
            print(f"* (-) Deleting item: {title}/{cre}")
            ddb_client.delete_item(
                TableName=table_name,
                Key={
                    "title": {'S': title},
                    "created": {'S': cre}
                }
            )
    
            # PUT ITS REPLACEMENT
            print(f"* (+) Putting replacement item: {title}/{cre}")
            item_d = ddbjson.dumps(recent_items[idx], as_dict=True)
            ddb_client.put_item(
                TableName=table_name,
                Item=item_d
            )
    else:
        print("* No items to update")

    # =====================================================================
    # WRITE INVALID ITEMS TO PASTEBIN
    # =====================================================================
    if len(invalid_items) > 0:
        print("* Writing invalid items to pastebin")
        ts = datetime.now().strftime('%Y%m%d-%H%M%S')
        paste_invalid = f'''
# Invalid Items ({ts})
'''
        
        for invalid_item in invalid_items:
            paste_invalid += "-\n"
            for k in invalid_item.keys():
                paste_invalid += f'  {k}: "{invalid_item[k]}"\n'
        
        payload_inv = {
            "title": f"invalid-items-{ts}.yaml",
            "content": paste_invalid
        }
        resp_inv = http.request('POST', omg_paste_url, body=json.dumps(payload_inv), headers=omg_headers)
    else:
        print("* No invalid items to save")

    # EXIT NOW IF NOTHING TO UPDATE
    if (not force) and (len(new_titles) == len(update_titles) == len(invalid_items) == 0):
        print("* No additions or updates to save (YAML paste unchanged). Exiting.")
        return None

    # =====================================================================
    # OVERWRITE THE mediaXX.yaml PASTE
    # =====================================================================
    print("* Writing recent items back to pastebin")
    ts = datetime.now().strftime('%Y%m%d-%H%M%S')
    paste_med = f'''
# media{content_version}.yaml (Updated {ts})
# Required attributes: title, type
# Optional attributes: created, modified, icon, url, progress, last-episode
'''

    for recent_item in recent_items:
        paste_med += "-\n"
        for k in recent_item.keys():
            paste_med += f'  {k}: "{recent_item[k]}"\n'
    
    payload_med = {
        "title": f"media{content_version}.yaml",
        "content": paste_med
    }
    resp_med = http.request('POST', omg_paste_url, body=json.dumps(payload_med), headers=omg_headers)

    # BEGIN TO CONSTRUCT THE NEW NOW CONTENT
    print("* Writing NOW content")
    now = '''
{profile-picture}
    
# Michael Burkhardt

## What I’m Doing Now

This is what I’ve been into lately.<br/>I also post a [weekly summary](https://blog.mihobu.lol/tag/weeknotes).

<script src="https://status.lol/mihobu.js?time&fluent&pretty&link"></script>

'''

    # GET RECENT ITEMS IN EACH CATEGORY
    for typ in ["R", "W", "L", "T"]: # In display order
        now += f"\n### {type_names[typ]}\n\n"
        now_items = sorted(filter_by_type(recent_items, typ), key=lambda x: x['modified'], reverse=True)
        if len(now_items) == 0:
            now += "- No recent items to show {otter}\n"
        else:
            for now_item in now_items:
                mod_date = datetime.strptime(now_item['modified'], '%Y%m%d-%H%M%S')
                ttts = mod_date.strftime('%Y-%m-%d')
                if 'url' in now_item.keys():
                    now += f"- [{now_item['title']}]({now_item['url']})"
                else:
                    now += f"- {now_item['title']}"
                if 'last-episode' in now_item.keys():
                    now += f" (Ep. {now_item['last-episode']})"
                if 'progress' in now_item.keys():
                    pr = now_item['progress']
                    now += f' <div class="progress-bar-container" style="--pct:{pr}%;" data-tooltip="{pr}% on {ttts}"></div>'
                if 'icon' in now_item.keys():
                    now += f" {{{now_item['icon']}}}\n"
                else:
                    now += f" {{otter}}\n"

    now += '''

<div class="nowlol"><a href="https://mihobu.lol/">HELLO</a> ⎮ <span>NOW</span> ⎮ <a href="https://blog.mihobu.lol/">BLOG</a></div>

{last-updated}

<div style="display:none"><a rel="me" href="https://social.lol/@mihobu">Mastodon</a></div>

<img id="dont-touch-image" src="https://mihobu.url.lol/profile-note" />
'''

    # CALL THE OMG.LOL API TO UPDATE THE NOW PAGE CONTENTS
    payload_now = {
        'content': now,
        'listed': 1
    }
    resp_now = http.request('POST', omg_now_url, body=json.dumps(payload_now), headers=omg_headers)

    print("* Done!")
