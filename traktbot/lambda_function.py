import boto3
import dynamodb_json as ddbjson
import json
import re
import sys
import urllib3
import uuid

from copy import deepcopy
from datetime import datetime, timedelta, timezone

# =====================================================================
# Remove non-alphabetic characters from attribute names
# =====================================================================
def conv_attr_str(instr):
    regex = re.compile('[^a-zA-Z]')
    #First parameter is the replacement, second parameter is your input string
    return regex.sub('', instr)

# =====================================================================
# FIND THE DICT WITH GIVEN k==v FROM A LIST, IF IT EXISTS.
# RETURN None OTHERWISE.
# =====================================================================
def find_item_in(test_list, k, v):
    return next((item for item in test_list if (k in item.keys()) and (item[k] == v)), None)

# =====================================================================
# RETURN THE VALUE FROM A DICT IN A GIVEN LIST IF THE NAME MATCHES
# =====================================================================
def get_value_from(test_list, name):
    return next((item['Value'] for item in test_list if item['Name'] == name), None)

# =====================================================================
# GET MY RATING FOR A GIVEN TRAKT ID
# =====================================================================
def get_rating(test_list, mitem):
    if mitem['type'] == 'movie':
        trakt_id = mitem['movie']['ids']['trakt']
    elif mitem['type'] == 'episode':
        trakt_id = mitem['episode']['ids']['trakt']
    else:
        return None

    for item in test_list:
        if (item['type'] == 'episode') and (str(item['episode']['ids']['trakt']) == str(trakt_id)):
            return item['rating']
        elif (item['type'] == 'movie') and (str(item['movie']['ids']['trakt']) == str(trakt_id)):
            return item['rating']
        else:
            continue
    
    return None

# =====================================================================
# LAMBDA HANDLER FUNCTION
# =====================================================================
def lambda_handler(event, context):

    #--
    #-- GET PARAMETERS FROM PARAMETER STORE
    #--
    ssm_client = boto3.client('ssm')
    parameters = [
      'TRAKT_ACCESS_TOKEN',
      'TRAKT_REFRESH_TOKEN',
      'TRAKT_CLIENT_ID',
      'TRAKT_CLIENT_SECRET',
      'TRAKT_HISTORY_INTERVAL'
    ]
    resp_ssm = ssm_client.get_parameters(Names=parameters)
    trakt_access_token = get_value_from(resp_ssm['Parameters'], 'TRAKT_ACCESS_TOKEN')
    trakt_refresh_token = get_value_from(resp_ssm['Parameters'], 'TRAKT_REFRESH_TOKEN')
    trakt_client_id = get_value_from(resp_ssm['Parameters'], 'TRAKT_CLIENT_ID')
    trakt_client_secret = get_value_from(resp_ssm['Parameters'], 'TRAKT_CLIENT_SECRET')
    display_days = int(get_value_from(resp_ssm['Parameters'], 'TRAKT_HISTORY_INTERVAL'))

    #--
    #-- CONFIGURE THE API URLS
    #--
    trakt_url        = "https://api.trakt.tv"
    token_url        = f"{trakt_url}/oauth/token"
    history_url      = f"{trakt_url}/users/mihobu/history"
    ratings_url      = f"{trakt_url}/users/mihobu/ratings"
    redirect_uri    = "urn:ietf:wg:oauth:2.0:oob"

    #--
    #-- OTHER CONFIGURATION
    #--
    table_name = 'now-content-v7'

    #--
    #-- CREATE A CONNECTION POOL
    #--
    http = urllib3.PoolManager()

    #--
    #-- GET TIMESTAMPS THAT WE'LL NEED
    #--
    utc = timezone(timedelta(hours=0))
    now_dt = datetime.now(tz=utc)
    starting_dt = now_dt - timedelta(days=display_days)
    start_at_trk = starting_dt.isoformat(timespec='seconds')
    start_at_ddb = starting_dt.strftime('%Y%m%d-000000')

    #--
    #-- GET TRAKT USER HISTORY
    #--
    headers_hst = {
        'Content-Type': 'application/json',
        'trakt-api-version': '2',
        'trakt-api-key': trakt_client_id,
        'Authorization': f'Bearer {trakt_access_token}'
    }
    params_hst = {
        'start_at': start_at_trk,
        'limit': 1000
        #'end_at': ''
    }
    resp_hst = http.request(
        'GET',
        url=history_url,
        headers=headers_hst,
        fields=params_hst
    )
    if resp_hst.status == 401:
        print("Need to refresh the access token")
        # NEED TO REFRESH THE ACCESS TOKEN
        payload_rfr = {
            "refresh_token": trakt_refresh_token,
            "client_id": trakt_client_id,
            "client_secret": trakt_client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "refresh_token"
        }
        headers_rfr = {
            'Content-Type': 'application/json',
            'trakt-api-version': '2',
            'trakt-api-key': trakt_client_id
        }
        resp_rfr = http.request(
            'POST',
            url=token_url,
            headers=headers_rfr,
            body=json.dumps(payload_rfr)
        )
        if resp_rfr.status == 200:
            rfr_content = json.loads(resp_rfr.data)
            new_access_token = rfr_content['access_token']
            new_refresh_token = rfr_content['refresh_token']
            resp_ssm = ssm_client.put_parameter(Name='TRAKT_ACCESS_TOKEN', Value=new_access_token)
            resp_ssm = ssm_client.put_parameter(Name='TRAKT_REFRESH_TOKEN', Value=new_refresh_token)
            trakt_access_token = new_access_token
            trakt_refresh_token = new_refresh_token

            # Try again
            resp_hst = http.request(
                'GET',
                url=history_url,
                headers=headers_hst,
                fields=params_hst
            )
        else:
            print("FAILED to refresh the access token")
    else:
        print("Access token OK")

    if resp_hst.status == 200:
        # Either first or second attempt was successful
        history = json.loads(resp_hst.data)
    else:
        raise Exception("FAILED to load Trakt user history")

    #--
    #-- GET USER RATINGS
    #--
    headers_rtg = {
        'Content-Type': 'application/json',
        'trakt-api-version': '2',
        'trakt-api-key': trakt_client_id
    }
    resp_rtg = http.request(
        'GET',
        url=ratings_url,
        headers=headers_rtg
    )
    ratings = []
    if resp_rtg.status == 200:
        ratings = json.loads(resp_rtg.data)

    #--
    #-- GET RECENT ITEMS FROM DYNAMODB
    #--
    ddb_client = boto3.client('dynamodb')
    ddb_resource = boto3.resource('dynamodb')
    ddb_table = ddb_resource.Table(table_name)

    resp = ddb_table.scan(
        TableName=table_name,
        Select='ALL_ATTRIBUTES',
        ExpressionAttributeNames={"#modified": "modified"},
        ExpressionAttributeValues={':START_AT': start_at_ddb},
        FilterExpression="#modified >= :START_AT"
    )
    recent_items_d = resp['Items']
    recent_items = ddbjson.loads(recent_items_d)
    print("* Loaded {} recent items from DynamoDB".format(len(recent_items)))

    #--
    #-- INITIALIZE SOME LISTS
    #--
    updated_items = [] # This is a list of partial items (modified attrs only)
    new_items     = [] # Complete items

    #--
    #-- COMPARE RECENT ITEMS WITH HISTORY ITEMS
    #--
    for item in sorted(history, key=lambda x: x['watched_at']):
        trakt_id = str(item['id'])
        recent_item = find_item_in(recent_items, 'trakt_id', trakt_id)
        watched_dt = datetime.fromisoformat(item['watched_at'][:-1]) # from Trakt history
        hist_watched_ts = watched_dt.strftime('%Y%m%d-%H%M%S')

        if recent_item is not None:
            # This item was found in DynamoDB
            updated_item = {}
            updated_item['id'] = recent_item['id']
            upd = False

            # Compare the watched date (history) with modified date (DynamoDB)
            if hist_watched_ts != recent_item['modified']:
                # we need to update this item in DynamoDB
                updated_item['modified'] = hist_watched_ts
                upd = True
                
            # Get user's rating
            rating = get_rating(ratings, item) # int or None
            if rating is not None:
                rating_s = str(round(rating/2))
                if ('rating' not in recent_item.keys()) or (rating_s != recent_item['rating']):
                    updated_item['rating'] = rating_s
                    upd = True
            
            # If there were changes
            if upd:
                updated_items.append(deepcopy(updated_item))

        else:
            # This item does not exist in DynamoDB (recent items) so we must add it as a new item
            print(f"Item with trakt_id={trakt_id} is new")
            new_item = {}
            new_item['id'] = str(uuid.uuid4())
            new_item['created'] = new_item['modified'] = hist_watched_ts
            new_item['type'] = 'W'
            new_item['trakt_id'] = trakt_id

            # Extract title and last-episode, and determine icon
            if item['type'] == 'movie':
                title = item['movie']['title']
                last_episode = None
                icon = 'film'
                slug = item['movie']['ids']['slug']
                url = f"https://trakt.tv/movies/{slug}"
            #elif item['type'] == 'show':
            #    title = item['show']['title']
            #    last_episode = None
            #    icon = 'tv'
            elif item['type'] == 'episode':
                title = item['show']['title']
                slug = item['show']['ids']['slug']
                s = item['episode']['season']
                e = item['episode']['number']
                last_episode = f"S{s}.E{e}"
                icon = 'tv'
                url = f"https://trakt.tv/shows/{slug}/seasons/{s}/episodes/{e}"
            #elif item['type'] == 'season':
            #    title = "{}, season {}".format(item['show']['title'], item['episode']['season'])
            #    last_episode = None
            #    icon = 'tv'
            else:
                continue

            new_item['title'] = title
            new_item['icon'] = icon
            new_item['url'] = url
            if last_episode is not None:
                new_item['last-episode'] = last_episode

            # Get user's rating
            rating = get_rating(ratings, item) # int or None
            if rating is not None:
                rating_s = str(round(rating/2))
                new_item['rating'] = rating_s

            new_items.append(deepcopy(new_item))

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
