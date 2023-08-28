import boto3
import dynamodb_json as ddbjson
import feedparser
import json
import re
import urllib3
import uuid
import yaml

from copy import deepcopy
from datetime import datetime, timedelta
from dateutil import tz

# =====================================================================
# Convert a timestamp string as it appears in the Goodreads RSS feed
# to a string of the form YYYYMMDD-HHMMSS
# =====================================================================
def ts_to_dtstr(ts):
    dt = datetime.strptime(ts, "%a, %d %b %Y %H:%M:%S %z")
    dt_utc = dt.astimezone(tz.gettz('UTC'))
    dt_utc_str = dt_utc.strftime("%Y%m%d-%H%M%S")
    return dt_utc_str

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
    #if ('rating' in input_item.keys()) and (input_item['rating'] != ""):
    #    try:
    #        rt = int(input_item['rating'])
    #        if rt not in range(1,6):
    #            raise ValueError
    #    except ValueError:
    #        is_valid = False
    return is_valid

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
    global req_attrs
    req_attrs = ['title', 'type']
    global opt_attrs 
    opt_attrs = ['id', 'icon', 'url', 'progress', 'last-episode', 'delete', 'rating', 'note', 'trakt_id']
    
    # DYNAMO DB CONFIG
    table_name = f"now-content-v{content_version}"
    
    # RSS FEED URL
    rss_url = "https://www.goodreads.com/user/updates_rss/6976996"

    oneweekago = datetime.now() - timedelta(days=display_days)
    owa_str = oneweekago.strftime('%Y%m%d-000000')

    #--
    #-- LOAD ITEMS FROM GOODREADS RSS FEED AND ADD TO THE INPUT ITEMS
    #--
    feed = feedparser.parse(rss_url)
    book_list = {}
    for entry in feed['entries'][::-1]:
        summary = entry['summary']
        book_progress = None
    
        # Skip old entries
        published = ts_to_dtstr(entry['published'])
        if published <= owa_str:
            continue
        
        # Extract book URL
        m1 = re.search('href="([^"]*)"', summary)
        if m1:
            book_url = m1.group(1)
        else:
            # Skip if no URL
            continue

        # Extract book title
        m2 = re.search('title="([^"]*)"', summary)
        if m2:
            book_title = m2.group(1)
        else:
            # Skip if no title
            continue
    
        # Started reading; don't overwrite book_progress is not present
        m2b = re.search('started reading', summary)
        if m2b:
            book_progress = 0
    
        # Extract book progress
        m3 = re.search('is (\d+)% done', summary)
        if m3:
            book_progress = int(m3.group(1))
        
        m3b = re.search('is on page (\d+) of (\d+)', summary)
        if m3b:
            book_progress = int( round( ( int(m3b.group(1)) / int(m3b.group(2)) ) * 100, 0) )

        # Book finished?
        m4 = re.search('finished reading', summary)
        if m4:
            book_progress = 100
        
        # Extract book rating
        m5 = re.search('gave (\d) star', summary) # scale of 5
        book_rating = int(m5.group(1)) if m5 else None
    
        # populate a dict in case the same title appears more than once
        if isinstance(book_progress,int) or book_rating:
            ts = datetime.now().strftime('%Y%m%d-%H%M%S')
            if book_url not in book_list.keys():
                book_list[book_url] = {} # create empty dict
            
            # book exists, overwrite with current values
            book_list[book_url]['id'] = book_url
            book_list[book_url]['title'] = book_title
            book_list[book_url]['type'] = 'B'
            book_list[book_url]['url'] = book_url
            book_list[book_url]['icon'] = 'book'
            if isinstance(book_progress, int):
                book_list[book_url]['progress'] = str(book_progress)
            if book_rating:
                book_list[book_url]['rating'] = str(book_rating)

    # BUILD input_items from book_list
    input_items = [v for v in book_list.values()]

    # GET DYNAMODB CLIENT
    ddb_client = boto3.client('dynamodb')
    ddb_resource = boto3.resource('dynamodb')
    ddb_table = ddb_resource.Table(table_name)

    #--
    #-- GET "RECENT" ITEMS FROM DYNAMODB
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
    print(">>> Loaded {} recent items from DynamoDB".format(len(recent_items)))
    
    #--
    #-- COMPARE INPUT ITEMS TO RECENT ITEMS
    #--
    updated_items    = [] # LIST OF UPDATED ITEMS, INCL. MODIFIED ATTRS ONLY
    new_items        = [] # LIST OF COMPLETE ITEMS
    for input_item in input_items:

        # Get the item's ID, if it exists
        item_id = get_value(input_item, 'id')

        # Look for the item ID in the list of recent items (from DynamoDB)
        recent_item = find_item_in(recent_items, 'id', item_id)
        if recent_item is None:
            # This is a new book. Add timestamps and append to new_items
            input_item['modified'] = ts
            input_item['created'] = ts
            new_items.append(deepcopy(input_item))
        else:
            # This is a recent item.
            # Check for differences between input_item and recent_item.
            # We're only looking at the input_item's keys here.
            upd = False
            updated_item = {}
            updated_item['id'] = item_id

            # Check for attributes in input_item (RSS) that are not in recent_item (DynamoDB)
            # If there are differences, input_item will take precedence
            for k in input_item.keys():
                if k in ['modified', 'created']:
                    # Ignore timestamps
                    continue
                if (k not in recent_item) or (recent_item[k] != input_item[k]):
                    print(f"*** Adding or updating attribute ({k}) for id={item_id}")
                    upd = True
                    updated_item[k] = str(input_item[k])

            if upd:
                updated_item['modified'] = datetime.now().strftime('%Y%m%d-%H%M%S')
                updated_items.append(deepcopy(updated_item))

    #--
    #-- INSERT NEW ITEMS IN DYNAMODB
    #--
    if len(new_items) > 0:
        for new_item in new_items:
            print(f"*** Adding new item: {new_item['title']}")
            new_item_d = ddbjson.dumps(new_item, as_dict=True)
            ddb_client.put_item(TableName=table_name, Item=new_item_d)
    else:
        print(">>> No new items to create")

    #--
    #-- UPDATE ITEMS IN DYNAMODB
    #--
    if len(updated_items) > 0:
        for updated_item in updated_items:
            item_id = updated_item['id']
            print(f"*** Updating item: id={item_id}")
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
            print("*** - UPDATE EXPR: ", upd_expr)
            
            ddb_client.update_item(
                TableName=table_name,
                Key={"id": {'S': item_id}},
                ExpressionAttributeValues=expr_attr_vals,
                ExpressionAttributeNames=expr_attr_nams,
                UpdateExpression=upd_expr
            )
    else:
        print(">>> No items to update")

    #--
    #-- IF THERE WERE ANY CHANGES, TRIGGER THE NOW PAGE CONTENT GENERATOR
    #--

    if (len(updated_items)>0) or (len(new_items)>0):
        print("*** Sending message to SQS queue (to trigger NOW page rebuild)")
        # GET SQS CLIENT
        sqs_client = boto3.client('sqs')
        resp_sqs = sqs_client.send_message(
            QueueUrl = 'https://sqs.us-east-2.amazonaws.com/400999793714/now-page-triggers',
            MessageBody = '{}'
        )
