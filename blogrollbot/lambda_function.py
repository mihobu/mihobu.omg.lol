import boto3
import datetime
import feedparser
import json
import re
import urllib3

from bs4 import BeautifulSoup
from dateutil.parser import parse
from tqdm import tqdm
from typing import List
from urllib.parse import urlparse

# =====================================================================
# =====================================================================
def remove_newlines(text):
    clean = re.compile('\n')
    return re.sub(clean, '', text)

# =====================================================================
# =====================================================================
def remove_html_tags(text: str) -> str:
    soup = BeautifulSoup(text, "html.parser")
    cleaned_text = soup.get_text()
    return remove_newlines(cleaned_text)

# =====================================================================
# =====================================================================
def get_base_url(feed_url: str) -> str:
    parsed_url = urlparse(feed_url)
    return f"{parsed_url.scheme}://{parsed_url.netloc}"

# =====================================================================
# =====================================================================
def strip_protocol(url: str) -> str:
    if url.startswith("https://"):
        return url.lstrip("https://")
    elif url.startswith("http://"):
        return url.lstrip("http://")
    return url

# =====================================================================
# =====================================================================
def read_websites(filename: str) -> List[str]:
    with open(filename, "r") as file:
        return file.read().splitlines()

# =====================================================================
# RETURN THE VALUE FROM A DICT IN A GIVEN LIST IF THE NAME MATCHES
# =====================================================================
def get_value_from(test_list, name):
    return next((item['Value'] for item in test_list if item['Name'] == name), None)

# =====================================================================
# =====================================================================
def lambda_handler(event, context):
    max_entries = 10
    today = datetime.datetime.today()
    three_months_ago = today - datetime.timedelta(days=10)

    #--
    #-- GET PARAMETERS FROM PARAMETER STORE
    #--
    
    ssm_client = boto3.client('ssm')
    parameters = [ 'OMG_API_KEY' ]
    resp_ssm = ssm_client.get_parameters(Names=parameters)
    omg_api_key = get_value_from(resp_ssm['Parameters'], 'OMG_API_KEY')
    
    #--
    #-- BUILD HTML CONTENT
    #-- 
    
    html = f"""
---
Date: {datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M")}
Type: Page
Location: /blogroll
---

# Blogroll

Here are the awesome weblogs that I enjoy reading regularly. Maybe you will too. Folks
who listed me on their blogroll get a cheeseburger. 🍔 If you’re a regular reader of my weblog and
I’ve left you off my list, **please** [let me know](https://contact.mihobu.lol/)!
"""
    websites = read_websites("feeds.txt")

    for website in websites:
        feed_url, feed_name = website.split('|')
        feed = feedparser.parse(feed_url)
        try:
            blog_link = feed['feed']['link']
            blog_title = feed['feed']['title']
        except Exception:
            print(f"Skipping feed: {website}")
            continue
        html += f"""
## [{feed_name}]({blog_link})

"""
        num_entries = 0
        for entry in feed.entries:
            if num_entries > max_entries:
                break
            try:
                post_link = entry.links[0]['href']
                #post_title = entry.title or "Untitled Post"
                post_title = entry.title or remove_html_tags(entry.summary)
                if len(post_title) > 40:
                    post_title = post_title[:40] + "..."
                d = entry.get("published") or entry.get("updated")
                published_date = parse(d, ignoretz=True, fuzzy=True)
            except Exception:
                print("Skipping post: ", post_link)
                continue
            if published_date >= three_months_ago:
                num_entries += 1
                html += f"""- {published_date.strftime("%Y-%m-%d %H:%M")} - [{post_title}]({post_link})\n"""
            
        if num_entries == 0:
            html += "- No recent posts\n"

    # OMG.LOL CONFIG
    omg_url = 'https://api.omg.lol/address/mihobu/weblog/entry/blogroll-lambda'
    omg_headers = { 'Authorization': f'Bearer {omg_api_key}' }
    
    # GET A CONNECTION POOL
    http = urllib3.PoolManager()
    
    # CALL THE OMG.LOL API TO UPDATE THE NOW PAGE CONTENTS
    payload = { 'content': html, 'listed': 1 }
    resp_now = http.request('POST', omg_url, body=json.dumps(payload), headers=omg_headers)
    
    print("Done!")


    return {}

