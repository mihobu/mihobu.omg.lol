import boto3
import dynamodb_json as ddbjson
import json
import os
import re
import urllib3
import uuid
import yaml

from copy import deepcopy
from datetime import datetime, timedelta

# =====================================================================
# FIND THE DICT WITH GIVEN k==v FROM A LIST, IF IT EXISTS.
# RETURN None OTHERWISE.
# =====================================================================
def find_item_in(test_list, k, v):
    return next((item for item in test_list if item[k] == v), None)

# =====================================================================
# VALIDATE THE CONTENTS OF A DICT.
# req_attrs AND opt_attrs MUST BE DEFINED
# =====================================================================
def validate_input_item(input_item):
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
    # Check rating attribute (only if not blank)
    if ('rating' in input_item.keys()) and (input_item['rating'] != ""):
        try:
            rt = int(input_item['rating'])
            if rt not in range(1,6):
                raise ValueError
        except ValueError:
            is_valid = False
    return is_valid

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
# GET THE VALUE FOR A GIVEN ATTRIBUTE IN A DICT, IF IT EXISTS
# RETURN None OTHERWISE
# =====================================================================
def get_value(test_item, k):
    return test_item[k] if k in test_item.keys() else None

# =====================================================================
# RETURN THE VALUE FROM A DICT IN A GIVEN LIST IF THE NAME MATCHES
# =====================================================================
def get_value_from(test_list, name):
    return next((item['Value'] for item in test_list if item['Name'] == name), None)

# =====================================================================
# Remove non-alphabetic characters from attribute names
# =====================================================================
def conv_attr_str(instr):
    regex = re.compile('[^a-zA-Z]')
    #First parameter is the replacement, second parameter is your input string
    return regex.sub('', instr)

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
    omg_paste_url = 'https://api.omg.lol/address/mihobu/pastebin'
    omg_api_key = os.environ['OMG_API_KEY']
    omg_headers = { 'Authorization': f'Bearer {omg_api_key}' }
    yaml_url = f"https://mihobu.paste.lol/media{content_version}.yaml/raw"
    
    # GET A CONNECTION POOL
    http = urllib3.PoolManager()
    
    # GET DYNAMODB CLIENT
    ddb_client = boto3.client('dynamodb')
    ddb_resource = boto3.resource('dynamodb')
    ddb_table = ddb_resource.Table(table_name)

    #--
    #-- LOAD THE USER'S YAML FILE FROM PASTEBIN
    #--
    resp = http.request('GET', yaml_url)
    input_items = yaml.load(resp.data, Loader=yaml.loader.BaseLoader) # force all to string
    if input_items is None:
        # YAML content is empty, so create empty list
        input_items = []
    print("* Loaded {} input items from pastebin".format(len(input_items)))

    #--
    #-- GET "RECENT" ITEMS FROM DYNAMODB
    #--
    oneweekago = datetime.now() - timedelta(days=display_days)
    owa_str = oneweekago.strftime('%Y%m%d-000000')
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
    
    #--
    #-- CREATE LISTS FOR NEW, UPDATED, AND INVALID ITEMS
    #--
    deleted_item_ids = [] # LIST OF ITEM ID STRINGS ONLY
    updated_items    = [] # LIST OF UPDATED ITEMS, INCL. MODIFIED ATTRS ONLY
    new_items        = [] # LIST OF COMPLETE ITEMS
    invalid_items    = [] # LIST OF COMPLETE ITEMS
    
    #--
    #-- COMPARE INPUT ITEMS TO RECENT ITEMS
    #--
    for input_item in input_items:

        # Validate the item
        if not validate_input_item(input_item):
            invalid_items.append(deepcopy(input_item))
            continue
    
        # Get the item's ID, if it exists
        item_id = get_value(input_item, 'id')
        
        if item_id is None:
            # This is a new item
            print(f"* Adding new item: {input_item['title']}")
            new_item = deepcopy(input_item)
            new_item['id'] = str(uuid.uuid4()) # create or overwrite the id attribute
            ts = datetime.now().strftime('%Y%m%d-%H%M%S')
            new_item['modified'] = ts
            new_item['created'] = ts
            new_items.append(deepcopy(new_item))
            continue
        
        else:
            # This item has an ID, but may or may not be a "recent" item

            # Check for delete flag
            if ('delete' in input_item.keys()) and (input_item['delete']=='yes'):
                deleted_item_ids.append(item_id)
                continue
    
            # Look for the item ID in the list of recent items (from DynamoDB)
            recent_item = find_item_in(recent_items, 'id', item_id)
            if recent_item is None:
                # This item is "old" and needs to be aged off
                print(f"* Aging off item: {input_item['title']}")
                #ewrite = True
            else:
                # This is a recent item
                # Check for differences between input_item and recent_item
                # We're only looking at the input_item's keys here
                upd = False
                updated_item = {}
                updated_item['id'] = item_id

                # Check for attributes in pastebin (input_item) that are not in DynamoDB (recent_item)
                # If there are *differences* pastebin will take precedence
                for k in input_item.keys():
                    if k in ['modified', 'created']:
                        # Ignore modified and created
                        continue
                    if (k not in recent_item) or (recent_item[k] != input_item[k]):
                        print(f"* Adding or updating attribute ({k}) for id={item_id}")
                        upd = True
                        updated_item[k] = str(input_item[k])

                # Check for attributes in DynamoDB (recent_item) that are not in pastebin (input_item)
                for k in recent_item.keys():
                    if k in ['modified', 'created']:
                        # Ignore modified and created
                        continue
                    if (k not in input_item):
                        print(f"* Adding or updating attribute ({k}) for id={item_id}")
                        upd = True
                        updated_item[k] = str(recent_item[k])

                if upd:
                    updated_item['modified'] = datetime.now().strftime('%Y%m%d-%H%M%S')
                    updated_items.append(deepcopy(updated_item))

    #--
    #-- DELETE ITEMS FROM DYNAMODB
    #--
    if len(deleted_item_ids) > 0:
        for item_id in deleted_item_ids:
            print(f"* (-) Deleting item: id={item_id}")
            ddb_client.delete_item(
                TableName=table_name,
                Key={"id": {'S': item_id}}
            )
    else:
        print("* No items to delete")

    #--
    #-- INSERT NEW ITEMS IN DYNAMODB
    #--
    if len(new_items) > 0:
        for new_item in new_items:
            print(f"* Adding new item: {new_item['title']}")
            new_item_d = ddbjson.dumps(new_item, as_dict=True)
            ddb_client.put_item(TableName=table_name, Item=new_item_d)
    else:
        print("* No new items to create")

    #--
    #-- UPDATE ITEMS IN DYNAMODB
    #--
    if len(updated_items) > 0:
        for updated_item in updated_items:
            item_id = updated_item['id']
            print(f"* (-) Updating item: id={item_id}")
            expr_attr_vals = {}
            expr_attr_nams = {}
            upd_exprs_set = [] # list of "attribute token = value token" strings for SET
            upd_exprs_rem = [] # list of attribute tokens to REMOVE
            for i, attr in enumerate(updated_item.keys()):
                if attr != 'id':
                    attr_alias = conv_attr_str(attr)
                    attr_token = f"#{attr_alias}"
                    valu_token = f":{attr_alias}"
                    expr_attr_nams[attr_token] = attr
                    if updated_item[attr] == "":
                        upd_exprs_rem.append(attr_token)
                    else:
                        expr_attr_vals[valu_token] = {'S': updated_item[attr] }
                        upd_exprs_set.append(f"{attr_token}={valu_token}")

            upd_expr = ""
            if len(upd_exprs_set) > 0:
                upd_expr += "SET " + ','.join(upd_exprs_set)
            if len(upd_exprs_rem) > 0:
                upd_expr += " REMOVE " + ','.join(upd_exprs_rem)
            print(" --> ", upd_expr)
            
            ddb_client.update_item(
                TableName=table_name,
                Key={"id": {'S': item_id}},
                ExpressionAttributeValues=expr_attr_vals,
                ExpressionAttributeNames=expr_attr_nams,
                UpdateExpression=upd_expr
            )
    else:
        print("* No items to update")

    #--
    #-- WRITE INVALID ITEMS TO PASTEBIN
    #--
    if len(invalid_items) > 0:
        print("* Writing invalid items to pastebin")
        ts = datetime.now().strftime('%Y%m%d-%H%M%S')
        paste_invalid = f'''# Invalid Items ({ts})'''
            
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

    #--
    #-- NOW DYNAMODB TABLE HAS BEEN UPDATED, RELOAD RECENT ITEMS FROM DYNAMODB
    #--
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

    #--
    #-- ALWAYS OVERWRITE THE mediaXX.yaml PASTE
    #--
    print("* Writing recent items back to pastebin")
    ts = datetime.now().strftime('%Y%m%d-%H%M%S')
    opt_attrs_str = ', '.join(opt_attrs)
    req_attrs_str = ', '.join(req_attrs)
    paste_med = f'''
# media{content_version}.yaml (Updated {ts})
# Required attributes: {req_attrs_str}
# Optional attributes: {opt_attrs_str}
'''

    for recent_item in sorted(recent_items, key=lambda x: x['modified'], reverse=True):
        paste_med += "-\n"
        for k in recent_item.keys():
            if k not in ['modified', 'created']:
                paste_med += f'  {k}: "{recent_item[k]}"\n'
    
    payload_med = {
        "title": f"media{content_version}.yaml",
        "content": paste_med
    }
    resp_med = http.request('POST', omg_paste_url, body=json.dumps(payload_med), headers=omg_headers)

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
        now += f"\n### {type_names[typ]}\n\n"
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
                    rt = int(now_item['rating'])
                    now += ' <div class="ratings-container"><span class="star-on">'
                    now += '★' * rt
                    now += '</span><span class="star-off">'
                    now += '★' * (5-rt)
                    now += '</span></div>'
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
