import boto3
import html2text
import json
import re
import requests
import urllib3
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
    
            # construct entry identifier
            entry = f"micro-{status['id']}"
    
            # Check to see if post already exists on weblog
            resp = http.request('GET', f"{omg_weblog_entry}/{entry}", headers=omg_headers)
            resp_d = json.loads(resp.data)
            if resp_d['request']['status_code'] == 200:
                print(f"Post ({entry}) already exists...skipping.")
                continue
    
            # construct a title
            plain = html2text.html2text(status['content'])
            plain = re.sub('\s*\n\s*|\s{2,}', ' ', plain.strip())
            if len(plain) > 53:
                title = f"{plain[:50]}..."
            else:
                title = plain
    
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
            c += f"{status['content']}\n\n"
            if len(status['media_attachments']) > 0:
                c += f"![]({status['media_attachments'][0]['url']})\n"
            c += f"""
<script>
const mastodonLink = "{status['url']}";
</script>
"""
    
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

    return {}
