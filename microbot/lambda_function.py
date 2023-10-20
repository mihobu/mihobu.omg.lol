import boto3
import dynamodb_json as ddbjson
import html2text
import json
import re
import requests
import urllib3
import uuid
from datetime import datetime, timedelta

# =====================================================================
# RETURN THE VALUE FROM A DICT IN A GIVEN LIST IF THE NAME MATCHES
# =====================================================================
def get_value_from(test_list, name):
    return next((item['Value'] for item in test_list if item['Name'] == name), None)

# =====================================================================
# =====================================================================
def lambda_handler(event, context):

    # MASTODON STUFF
    statuses_url = "https://social.lol/api/v1/accounts/109619824930798742/statuses"

    #--
    #-- GET PARAMETERS FROM PARAMETER STORE
    #--
    ssm_client = boto3.client('ssm')
    parameters = [
      'OMG_API_KEY',
      'MICROBLOG_SINCE_ID'
    ]
    resp_ssm = ssm_client.get_parameters(Names=parameters)
    omg_api_key = get_value_from(resp_ssm['Parameters'], 'OMG_API_KEY')
    since_id = get_value_from(resp_ssm['Parameters'], 'MICROBLOG_SINCE_ID')

    # OMGLOL STUFF
    omg_weblog_entry = f"https://api.omg.lol/address/mihobu/weblog/entry"
    omg_headers = { 'Authorization': f'Bearer {omg_api_key}' }
    
    # GET A CONNECTION POOL
    http = urllib3.PoolManager()

    # DYNAMO DB CONFIG
    table_name = f"now-content-v7"

    # GET DYNAMODB CLIENT
    ddb_client = boto3.client('dynamodb')
    ddb_resource = boto3.resource('dynamodb')
    ddb_table = ddb_resource.Table(table_name)

    # Dynamo DB
    num_new_items = 0

    while True:
        
        # CONSTRUCT QUERY AND GET STATUSES FROM API
        query = f"?since_id={since_id}"
        print(f"Query: {query}")
        response_statuses = requests.get(f"{statuses_url}{query}")
        statuses = response_statuses.json()
    
        # BREAK OUT IF NO STATUSES RETURNED
        if len(statuses) == 0:
            break
    
        print(f"{len(statuses)} statuses returned.")
        for status in statuses:
    
            # Extract a list of this status's tags in lowercase
            status_tags = [ctag['name'].lower() for ctag in status['tags']]

            # Find and store highest status ID --> since_id
            if status['id'] > since_id:
                since_id = status['id']
    
            # Ignore replies
            if status['in_reply_to_id'] is not None:
                print(f"Post {status['id']} is a reply...skipping")
                continue
    
            # Ignore reblogs (reposts)
            if status['reblog'] is not None:
                print(f"Post {status['id']} is a reblog...skipping")
                continue
    
            # Ignore posts tagged with "weeknotes" or "weblog"
            ignore_tags = ["weeknotes", "weblog"]
            if any(t in status_tags for t in ignore_tags):
                print(f"Post {status['id']} is has an ignored tag...skipping")
                continue

            # construct entry identifier
            entry = f"micro-{status['id']}"
    
            # Check to see if post already exists on weblog - just in case
            resp = http.request('GET', f"{omg_weblog_entry}/{entry}", headers=omg_headers)
            resp_d = json.loads(resp.data)
            if resp_d['request']['status_code'] == 200:
                print(f"Post ({entry}) already exists...skipping.")
                continue

            # Extract title and content
            content_md = html2text.html2text(status['content'], bodywidth=0) # extract markdown

            # Split on first newline
            separate_title = False
            reres = re.search("^([^\n]+)\n+", content_md)
            if reres is not None:
                # Extract the first line as the title, and the rest as the content
                title = reres[1]
                content = content_md[reres.end(0):]
                separate_title = True
            else:
                # No newline present, so construct a title
                plain = re.sub('\s*\n\s*|\s{2,}', ' ', content_md.strip())
                if len(plain) > 53:
                    title = f"{content_md[:50]}..."
                else:
                    title = content_md[:50]
                content = content_md[50:]

            # NOW WE'VE GOT THE TITLE AND CONTENT
            
            # Look for one my my "special" tags
            tag_icons = {
                'reading'  : 'book-open',
                'listening': 'volume-high',
                'tinkering': 'gears'
            }
            found_tag = None
            for ctag in [x['name'].lower() for x in status['tags']]:
                if ctag in tag_icons.keys():
                    found_tag = ctag
                    break
            if found_tag is not None:
                # Post is tagged with one of my special tags
                print(f"Post {status['id']} is tagged with {found_tag}...updating DynamoDB")
                ts = datetime.now().strftime('%Y%m%d-%H%M%S')
                num_new_items = num_new_items + 1
                new_item = {
                    "title": title,
                    "type": found_tag[0].upper(), # capitalized first letter of tag
                    "icon": tag_icons[found_tag],
                    "id": str(uuid.uuid4()),
                    "modified": ts,
                    "created": ts
                }
                if status['card'] is not None:
                    new_item['url'] = status['card']['url']
                print(f"*** Adding new item to DynamoDB: {new_item['title']}")
                new_item_d = ddbjson.dumps(new_item, as_dict=True)
                ddb_client.put_item(TableName=table_name, Item=new_item_d)

            else:
                # Treat as an ordinary post
                
                # construct tags
                tags = "Microblog"
                if len(status['media_attachments']) > 0:
                    tags += ", Pics"
                for stag in status['tags']:
                    tags += f", {stag['name']}"
    
                # Construct post content
                c = "---\n"
                ts = datetime.strptime(status['created_at'][:19], "%Y-%m-%dT%H:%M:%S")#.strftime("%Y-%m-%d %H:%M:%S")
                c += f"Date: {ts}\n"
                c += f"Tags: {tags}\n"
                c += f"Title: {title}\n"
                c += f"Slug: {entry}\n"
                c += "---\n\n"
                if separate_title:
                    c += f"{title}\n\n"
                c += f"{content}\n\n"
                if len(status['media_attachments']) > 0:
                    c += f"![]({status['media_attachments'][0]['url']})\n"
                #c += f"""
                #<script>
                #const mastodonLink = "{status['url']}";
                #</script>
                #"""

                # Write post to weblog
                resp2 = http.request('POST', f"{omg_weblog_entry}/{entry}", body=c.encode('utf-8'), headers=omg_headers)
                resp2_d = json.loads(resp2.data)
                if resp2_d['request']['status_code'] != 200:
                    raise Exception(f"*** ERROR *** while attempting to create entry ({entry})")
                print(f"Successfully posted {entry} to weblog.")
    

    # WRITE SINCE_ID TO PARAMETER STORE
    resp4 = ssm_client.put_parameter(
        Name='MICROBLOG_SINCE_ID',
        Value=since_id,
        Overwrite=True
    )

    #--
    #-- IF THERE WERE ANY CHANGES, TRIGGER THE NOW PAGE CONTENT GENERATOR
    #--

    if num_new_items > 0:
        print("*** Sending message to SQS queue (to trigger NOW page rebuild)")
        # GET SQS CLIENT
        sqs_client = boto3.client('sqs')
        resp_sqs = sqs_client.send_message(
            QueueUrl = 'https://sqs.us-east-2.amazonaws.com/400999793714/now-page-triggers',
            MessageBody = '{}'
        )

    return {}
