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
def has_tag(p, tag):
    tags = []
    meta = json.loads(p['metadata'])
    if 'tags' in meta.keys():
        tags = [t.lower() for t in meta['tags'].keys()]
    return tag in tags

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
    if resp.status != 200:
        raise Exception(f"*** ERROR {resp.status} while attempting to get weblog entries.")
    weblog_response = json.loads(resp.data)
    weblog_entries = weblog_response['response']['entries']
    print(f"--- Loaded {len(weblog_entries)} weblog entries.")
    
    #--
    #-- EXTRACT LIVE POSTS
    #--
    
    all_posts = sorted(filter(lambda we: (we['status'].lower()=="live")and(we['type'].lower()=="post"), weblog_entries), key=lambda x: x['date'], reverse=True)
    print(f"--- Loaded {len(all_posts)} live posts.")
    
    #--
    #-- SEPARATE POSTS BY TYPE; CONSTRUCT LISTS INDICES INTO posts
    #--
    
    featured_post   = None
    microblog_posts = []
    regular_posts   = []

    for ix, p in enumerate(all_posts):
        if (featured_post is None) and has_tag(p, 'feature'):
            featured_post = ix
        elif has_tag(p, 'microblog'):
            microblog_posts.append(ix)
        else:
            regular_posts.append(ix)

    #--
    #-- ARE THERE ANY NEW WEBLOG POSTS?
    #--
    
    last_post_date = max([post['date'] for post in all_posts])
    print(f"--- Last post date       : {last_post_date}")
    print(f"--- Weblog last timestamp: {weblog_last_ts}")
    if (last_post_date <= weblog_last_ts) and not force_rebuild:
        print("--- No new weblog entries...Exiting")
        return {}

    # Timestamp we'll use on both pages
    page_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

    # ==========================================================================
    # --- PART 1.2 MICROBLOG CONTENT ---
    # ==========================================================================

    mbpc = f"""---
Date: {page_ts}
Type: Page
Status: live
Title: Microblog
Location: /microblog
---
"""

    mbpc += """
# Microblog

This page contains a mirror of recent toots from my [Mastodon](https://social.lol/@mihobu) account.

<div class="landing-container">

"""
    for postnum, ix in enumerate(microblog_posts[:5]):
        post = all_posts[ix]
        post_date = datetime.utcfromtimestamp(post['date'])
        post_ts  = post_date.strftime("%Y-%m-%d %H:%M")
        mbpc += f"""
<div class="cell cell3"> <!-- MICROBLOG POST #{postnum} -->

{post['body']}

<p><aside class="post-info"><i class="mb-icons mb-clock"></i><a href="{post['location']}">{post_ts}</a></aside></p>

</div> <!-- MICROBLOG POST #{postnum} -->
"""

    mbpc += """
</div> <!-- landing-container -->

## More Microblog

<ul class="mb-ul">
  <li class="mb-icons mb-mastodon"><a href="https://social.lol/@mihobu">Interact with me on Mastodon</a></li>
  <li class="mb-icons mb-tag"><a href="/tag/microblog">Archive of my past toots</a></li>
</ul>

</div> <!-- microblog -->
</div> <!-- landing-container -->
"""

    # ==========================================================================
    # --- PART 1.3 Delete the old microblog page ---
    # ==========================================================================

    resp13 = http.request(
        method='DELETE',
        url=OMG_API_URL("mihobu","weblog/delete/microblog"),
        body=None,
        headers=omg_headers
    )
    resp13_d = json.loads(resp13.data)
    if resp13_d['request']['status_code'] != 200:
        raise Exception(f"*** ERROR *** while attempting to delete the old microblog page")
    print(f"Successfully deleted the old microblog page.")
    
    # ==========================================================================
    # --- PART 1.4 CREATE NEW MICROBLOG PAGE ---
    # ==========================================================================

    resp14 = http.request(
        method='POST',
        url=OMG_API_URL("mihobu","weblog/entry/microblog"),
        body=mbpc.encode('utf-8'),
        headers=omg_headers
    )
    resp14_d = json.loads(resp14.data)
    if resp14_d['request']['status_code'] != 200:
        raise Exception(f"*** ERROR *** while attempting to create new microblog page")
    print(f"Successfully created new microblog page.")

    # ==========================================================================
    # --- CONSTRUCT STATIC BLOG PAGE CONTENT
    # ==========================================================================

    wlpc = f"""---
Date: {page_ts}
Type: Page
Status: live
Title: Weblog
Location: /blog
---
"""

    # ==========================================================================
    # --- PART 2.2 FEATURED POST ---
    # ==========================================================================

    post = all_posts[featured_post]
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
    
    wlpc += f"""
<div class="landing-container">

<div class="cell cell1c"> <!-- FEATURED POST -->
<div class="landing-page-category">Featured Post • {post_lts}</div>

{fpcontent}

[Continue reading...]({post['location']})

</div> <!-- FEATURED POST -->
</div> <!-- landing-container -->
"""

    # ==========================================================================
    # --- PART 2.3 RECENT POSTS ---
    # ==========================================================================
    
    wlpc += """

# Recent Posts

<div class="landing-container">

"""

    for postnum, ix in enumerate(regular_posts[:6]):
        post = all_posts[ix]
        post_date = datetime.utcfromtimestamp(post['date'])
        post_ts  = post_date.strftime("%Y-%m-%d %H:%M")
        meta = json.loads(post['metadata'])
        abstract = meta['abstract'] if 'abstract' in meta.keys() else 'No description available'
    
        wlpc += f"""
<div class="cell cell3"> <!-- POST CARD #{postnum} -->

## [{post['title']}]({post['location']})

{abstract}

<p><aside class="post-info"><i class="mb-icons mb-clock"></i><a href="{post['location']}">{post_ts}</a></aside></p>

</div> <!-- POST CARD #{postnum} -->
"""

    wlpc += """
</div> <!-- landing-container -->
"""

    # ==========================================================================
    # --- ARCHIVE (LIST) OF REMAINING "REGULAR" BLOG POSTS
    # ==========================================================================

    wlpc += """
<h1>Weblog Archive</h1>
<table class="archive-post-list">
<tr><th>#</th><th>Date</th><th>Post</th></tr>
"""

    for postnum, ix in enumerate(regular_posts[6:]):
        post = all_posts[ix]
        post_date = datetime.utcfromtimestamp(post['date'])
        post_ts  = post_date.strftime("%Y-%m-%d %H:%M")
        wlpc += f"""<tr><td></td><td>{post_ts}</td><td><a href="{post['location']}">{post['title']}</a></td></tr>\n"""

    wlpc += "</table>\n"

    # --- PART 2.4 DELETE THE OLD WEBLOG PAGE ---

    resp24 = http.request(
        method='DELETE',
        url=OMG_API_URL("mihobu","weblog/delete/weblog"),
        body=None,
        headers=omg_headers
    )
    resp24_d = json.loads(resp24.data)
    if resp24_d['request']['status_code'] != 200:
        raise Exception(f"*** ERROR *** while attempting to delete the old weblog page")
    print(f"Successfully deleted the old weblog page.")
    
    # --- PART 2.5 CREATE A NEW WEBLOG PAGE ---

    resp25 = http.request(
        method='POST',
        url=OMG_API_URL("mihobu","weblog/entry/weblog"),
        body=wlpc.encode('utf-8'),
        headers=omg_headers
    )
    resp25_d = json.loads(resp25.data)
    if resp25_d['request']['status_code'] != 200:
        raise Exception(f"*** ERROR *** while attempting to create new weblog page")
    print(f"Successfully created new weblog page.")
    
    #--
    #-- Store weblog_last_ts in Parameter store
    #--

    weblog_last_ts
    resp4 = ssm_client.put_parameter(
        Name='WEBLOG_LAST_TS',
        Value=str(last_post_date),
        Overwrite=True
    )
    
    return {}
