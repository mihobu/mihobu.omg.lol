import boto3
import hashlib
import json
import os
import re
import urllib3
from datetime import datetime, timezone

# =====================================================================
# RETURN THE VALUE FROM A DICT IN A GIVEN LIST IF THE NAME MATCHES
# =====================================================================
def get_value_from(test_list, name):
    return next((item['Value'] for item in test_list if item['Name'] == name), None)

# =====================================================================
# =====================================================================
def OMG_API_URL(address, prefix, key=None):
    url = f"https://api.omg.lol/address/{address}/{prefix}"
    if key is not None:
        url += f"/{key}"
    return url

# =====================================================================
# =====================================================================
def lambda_handler(event, context):

    #--
    #-- FORCE REBUILD?
    #--
    force_rebuild = False
    if 'force' in event.keys():
        force_rebuild = True

    #--
    #-- GET PARAMETERS FROM PARAMETER STORE
    #--
    ssm_client = boto3.client('ssm')
    parameters = [
      'OMG_API_KEY',
      'WEBLOG_LAST_TS'
    ]
    resp_ssm = ssm_client.get_parameters(Names=parameters)
    omg_api_key = get_value_from(resp_ssm['Parameters'], 'OMG_API_KEY')
    weblog_last_ts = int(get_value_from(resp_ssm['Parameters'], 'WEBLOG_LAST_TS'))
    omg_headers = { 'Authorization': f'Bearer {omg_api_key}' }

    #--
    #-- GET A CONNECTION POOL
    #--
    http = urllib3.PoolManager()
    
    #--
    #-- GET THE WEBLOG ENTRIES. YES, ALL OF THEM.
    #--
    resp = http.request(
        method='GET',
        url=OMG_API_URL("mihobu","weblog/entries"),
        body=None,
        headers=omg_headers
    )
    weblog_response = json.loads(resp.data)
    weblog_entries = weblog_response['response']['entries']
    print(f"--- Loaded {len(weblog_entries)} weblog entries.")
    
    #--
    #-- EXTRACT LIVE POSTS
    #--
    posts = list(filter(lambda we: (we['status']=="live")and(we['type']=="post"), weblog_entries))
    print(f"--- Loaded {len(posts)} live posts.")
    
    #--
    #-- SEPARATE POSTS BY TYPE; CONSTRUCT LISTS INDICES INTO posts
    #--
    feature_posts   = []
    microblog_posts = []
    other_posts     = []

    for ix, p in enumerate(posts):
        meta = json.loads(p['metadata'])
        if 'tags' not in meta.keys():
            other_posts.append(ix)
            continue
        tags = list(meta['tags'].keys())
        if ('feature' in tags) and (len(feature_posts)==0):
            feature_posts.append(ix)
        elif 'microblog' in tags:
            microblog_posts.append(ix)
        else:
            other_posts.append(ix)
    
    #--
    #-- ARE THERE ANY NEW WEBLOG POSTS?
    #--
    last_post_date = max([post['date'] for post in posts])
    print(f"--- Last post date       : {last_post_date}")
    print(f"--- Weblog last timestamp: {weblog_last_ts}")
    if (last_post_date <= weblog_last_ts) and not force_rebuild:
        print("--- No new weblog entries...Exiting")
        return {}

    #--
    #-- CONSTRUCT STATIC LANDING PAGE CONTENT
    #--
    
    # --- PART 1. METADATA -----------------------------------------------------
    page_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    slpc = f"""---
Date: {page_ts}
Type: Page
Status: live
Title: Home
Location: /landing-page
---
"""

    # --- PART 2. FEATURED POST ------------------------------------------------
    post = posts[feature_posts[0]]
    post_date = datetime.utcfromtimestamp(post['date'])
    post_lts = post_date.strftime("%A, %d %B %Y")
    
    md = post['body']
    reres = re.search("<!-- CUT -->", md, re.MULTILINE)
    if reres is not None:
        print(f'Cut point found at {reres.start(0)}')
        fpcontent = md[:reres.start(0)]
    else:
        # This isn't working correctly
        print('No cut point found')
        fpcontent = post['body']
    
    slpc += f"""
<div class="landing-container">

<div class="cell cell1c"> <!-- FEATURED POST -->
<div class="landing-page-category">Featured Post • {post_lts}</div>

{fpcontent}

[Continue reading...]({post['location']})

</div> <!-- FEATURED POST -->
"""

    # --- PART 3. MICROBLOG ----------------------------------------------------
    slpc += """<div class="cell cell3"> <!-- MICROBLOG -->

# My Microblog Feed

"""
    for ix in microblog_posts[:5]:
        post = posts[ix]
        post_date = datetime.utcfromtimestamp(post['date'])
        post_ts  = post_date.strftime("%Y-%m-%d %H:%M")
        slpc += f"""
{posts[ix]['body']}

<p><aside class="post-info"><i class="fa-solid fa-clock"></i><a href="{post['location']}">{post_ts}</a></aside></p>

<div style="border-top:1px solid #999;"></div>
"""

    slpc += """

## More Microblog

<ul class="fa-ul">
  <li><span class="fa-li"><i class="fa-brands fa-mastodon"></i></span><a href="https://social.lol/@mihobu">Interact with me on Mastodon</a></li>
  <li><span class="fa-li"><i class="fa-solid fa-tag"></i></span><a href="/tag/microblog">Archive of my past toots</a></li>
</ul>

</div> <!-- microblog -->

"""

    # --- PART 4. RECENT POSTS -------------------------------------------------
    slpc += """<div class="cell cell3"> <!-- RECENT POSTS -->

# Recent Weblog Posts

"""
    for ix in other_posts[:5]:
        post = posts[ix]
        post_date = datetime.utcfromtimestamp(post['date'])
        post_ts  = post_date.strftime("%Y-%m-%d %H:%M")
        meta = json.loads(post['metadata'])
        abstract = meta['abstract'] if 'abstract' in meta.keys() else 'No description available'
    
        slpc += f"""

## [{post['title']}]({post['location']})

{abstract}

<p><aside class="post-info"><i class="fa-solid fa-clock"></i><a href="{post['location']}">{post_ts}</a></aside></p>

<div style="border-top:1px solid #999;"></div>
"""

    slpc += """
## More Weblog

<ul class="fa-ul">
  <li><span class="fa-li"><i class="fa-solid fa-tags"></i></span><a href="/tags">Browse Posts by Tag</a></li>
  <li><span class="fa-li"><i class="fa-solid fa-paper-plane"></i></span><a href="/tag/weeknotes">Weeknotes Archive</a></li>
  <li><span class="fa-li"><i class="fa-solid fa-scroll"></i></span><a href="/blogroll">Blogroll</a></li>
  <li><span class="fa-li"><i class="fa-solid fa-circle-nodes"></i></span><a href="/webrings">Webrings</a></li>
</ul>

</div> <!-- RECENT POSTS -->

"""

    # --- PART 4. THE REST -----------------------------------------------------
    slpc += """
<div class="cell cell-break"></div>

<div class="cell cell3"> <!-- FEATURED CONTENT -->
<h1>Featured Content</h2>
<ul class="fa-ul">
<li><span class="fa-li"><i class="fa-solid fa-circle-user"></i></span><b><a href="/hello">About Me</a></b></li>
<li><span class="fa-li"><i class="fa-solid fa-person-running"></i></span><b><a href="/now">What I’m Doing Now</a></b></li>
<li><span class="fa-li"><i class="fa-solid fa-suitcase"></i></span><a href="/uses">My Indispensable Stuff</a></li>
<li><span class="fa-li"><i class="fa-solid fa-thumbs-up"></i></span><a href="/social-media-survey">Social Media Survey</a></li>
<li><span class="fa-li"><i class="fa-solid fa-ranking-star"></i></span><a href="/my-content-rating-system">My Content Rating System</a></li>
<li><span class="fa-li"><i class="fa-solid fa-download"></i></span><a href="/downloads">Downloads</a></li>
<li><span class="fa-li"><i class="fa-solid fa-calendar-week"></i></span><a href="/calendar">ISO Week Calendar</a></li>
</ul>
</div> <!-- FEATURED CONTENT -->

<div class="cell cell3"> <!-- OTHER PROJECTS -->
<h1>Other Projects</h1>
<ul class="fa-ul">
<li><span class="fa-li"><i class="fa-solid fa-kitchen-set"></i></span><b><a href="https://rwau.cc">Recipes We Actually Use</a></b></li>
<li><span class="fa-li"><i class="fa-solid fa-book"></i></span><a href="https://monkeywalk.com/tps-frequency-dictionary-of-mandarin-chinese">TPS Frequency Dictionary of Mandarin Chinese</a></li>
<li><span class="fa-li"><i class="fa-solid fa-dragon"></i></span><a href="https://monkeywalk.com/eating-the-dragon">Eating the Dragon</a></li>
<li><span class="fa-li"><i class="fa-solid fa-vr-cardboard"></i></span><a href="https://mihobu.lol/tag/stereoscopy">Sterescopic Imaging Project</a></li>
</ul>
</div> <!-- OTHER PROJECTS -->

</div> <!-- landing-container -->
"""

    #--
    #-- Delete the old landing page
    #--
    resp2 = http.request(
        method='DELETE',
        url=OMG_API_URL("mihobu","weblog/delete/landing-page"),
        body=None,
        headers=omg_headers
    )
    resp2_d = json.loads(resp2.data)
    if resp2_d['request']['status_code'] != 200:
        raise Exception(f"*** ERROR *** while attempting to delete the old landing page")
    print(f"Successfully deleted the old landing page.")
    
    #--
    #-- Create a new landing page
    #--
    resp3 = http.request(
        method='POST',
        url=OMG_API_URL("mihobu","weblog/entry/landing-page"),
        body=slpc.encode('utf-8'),
        headers=omg_headers
    )
    resp3_d = json.loads(resp3.data)
    if resp3_d['request']['status_code'] != 200:
        raise Exception(f"*** ERROR *** while attempting to create new landing page")
    print(f"Successfully created new landing page.")
    
    #--
    #-- Store weblog_last_ts in Parameter store
    weblog_last_ts
    resp4 = ssm_client.put_parameter(
        Name='WEBLOG_LAST_TS',
        Value=str(last_post_date),
        Overwrite=True
    )
    
    return {}
