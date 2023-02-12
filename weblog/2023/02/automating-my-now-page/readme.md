---
Date: 2023-02-01 16:40
Tags: Photography
Stub: automating-my-now-page
---

# Automating My Now Page

## What is a Now page?

According to [nownownow.com](https://nownownow.com/about), a now page “tells you what this person is focused on at this point in their life.” I use [my now page](https://mihobu.monkeywalk.com/now) to share [my current status](https://mihobu.status.lol/) and the things I’ve recently read, watched, or listened to.

## Keeping It Simple

A lot of folks use a variety of tools to automate the capture of their various listening/viewing/watching activity. I’m too lazy to set all that up, so I’m starting simple. I created a YAML file in my [pastebin](https://paste.lol) that I can easily edit by hand. Here's a sample:

```
listen:
  -
    date: 20230212
    icon: microphone-lines
    title: The Foreign Desk No. 476
    url: https://monocle.com/radio/shows/the-foreign-desk/476
read:
  -
    date: 20230124
    icon: book
    title: "*The Dark Forest*, by Cixin Liu"
    url: https://www.goodreads.com/book/show/23168817-the-dark-forest
watch:
  -
    date: 20230211
    icon: futbol
    title: Brentford FC (EPL)
    url: https://www.brentfordfc.com/en
```

As you can see, each entry stores the date, icon, link text, and URL. I’m not actually doing anything with the date right now. Maybe someday. The `icon` can be any of the available [FontAwesome free icons](https://fontawesome.com/search?o=r&m=free).

## Scripting the Automation

I use Python a lot these days, so it was the easiest for me to work with. The idea is simple (and so, in fact, is the script): load the YAML file, generate markdown, upload to the omg.lol `/now` [API](https://api.omg.lol).

Here's the code (`nowbot.py`):

```
import boto3
import hashlib
import json
import urllib3
import yaml

def lambda_handler(event, context):

    # OMG.LOL API CONFIG
    omg_now_url = 'https://api.omg.lol/address/mihobu/now'
    omg_api_key = 'XXXXXXXXXXXXXXXXXXXXXXX'
    omg_headers = {
        'Authorization': f'Bearer {omg_api_key}'
    }
    
    # CONFIGURE HEADINGS
    heading = {
        "listen": "What I’m Listening To",
        "read": "What I’m Reading",
        "watch": "What I’m Watching"
    }
    
    # GET A CONNECTION POOL
    http = urllib3.PoolManager()
    
    # GET AN SSM CLIENT
    ssm_client = boto3.client('ssm')
    
    # OBTAIN OLD YAML DIGEST FROM THE PARAMETER STORE
    try:
        response = ssm_client.get_parameter(Name='nowbot_digest')
        old_digest = response['Parameter']['Value']
    except Exception as e:
        print(e)
        print("Ignored.")
        old_digest = 'UndefinedDigestValue'

    # GET THE MEDIA YAML FILE
    resp = http.request('GET', 'https://mihobu.paste.lol/media.yaml/raw')
    media2 = yaml.safe_load(resp.data)
    new_digest = hashlib.md5(resp.data).hexdigest()
    
    # HAVE THE CONTENTS CHANGED?
    if old_digest == new_digest:
        # YAML hasn't changed
        print('YAML content has not changed. Exiting.')
        return None

    # BEGIN TO CONSTRUCT THE NEW NOW CONTENT
    now = '''{profile-picture}
    
# Michael Burkhardt
    
## What I’m Doing Now
    
<script src="https://status.lol/mihobu.js?time&fluent&pretty&link"></script>
'''

    # LOOP OVER THE YAML CONTENT TO BUILD THE NEW NOW CONTENT
    max_items = 5
    for t in media2.keys():
        now += f"\n## {heading[t]}\n\n"
        c = 0
        for item in media2[t]:
            c = c + 1
            now += "- [{}]({}) {{{}}}\n".format(item['title'], item['url'], item['icon'])
            if c >= max_items:
                break

    # WRAP IT UP
    now += '''
<div class="nowlol">BACK TO <a href="https://mihobu.monkeywalk.com/">ALL THINGS MIHOBU</a></div>
{last-updated}
'''

    # CALL THE OMG.LOL API TO UPDATE THE NOW PAGE CONTENTS
    payload = {
        'content': now,
        'listed': 1
    }
    resp2 = http.request('POST', omg_now_url, body=json.dumps(payload), headers=omg_headers)

    # UPDATE THE MD5 DIGEST IN THE PARAMETER STORE
    response = ssm_client.put_parameter(
        Name='nowbot_digest',
        Value=new_digest,
        Overwrite=True
    )
```

Good coding practice suggests that I store my API key in AWS Secrets Manager. And it’s very easy to do. It’s also not trivially cheap. Running the Lambda function costs pennies per month, but storing a secret in Secrets Manager costs 40 cents! So yes, I hardcoded my key.

## Missing Library

Setting up the Lambda function was very easy using the AWS Console, but I ran into one snag:

```
[ERROR] Runtime.ImportModuleError: Unable to import module 'lambda_function': No module named 'yaml'
Traceback (most recent call last):
```

Crud. That means I need to create a [Lambda Layer](https://docs.aws.amazon.com/lambda/latest/dg/configuration-layers.html) containing the missing library (or libraries).

Lambda provides a lot Python libraries by default, but not everything you might every want. A Lambda Layers is basically just a ZIP file with a `site-packages` directory containing additional libraries you want to use.

To create my Lambda Layer, I simply installed packages to a specified directory on my Mac.

```
% pip install pyyaml --target ./python/lib/python3.9/site-packages --no-deps --no-binary=:all:
```

The directory must be [one that AWS Lambda recognizes](https://docs.aws.amazon.com/lambda/latest/dg/configuration-layers.html#configuration-layers-path) for the particular runtime in use—in this case, Python 3.9. I wanted to make sure I was explicitly adding all the libraries I needed, so that’s why I used the `--no-deps` option. Binary packages must be handled a little differently, thus the `--no-binary` option. (I didn’t any binary packages for this example, so I don’t cover that here. Maybe another post some day.)

Since I didn’t run into any other dependencies and Lambda didn’t complain about any of my other libraries, all that was left was to ZIP up the contents.

```
% zip -r layer.zip python
```

Creating the Layer in the Lambda service page of the AWS Console is very easy. Give the layer a name, upload the ZIP file, and define the compatible architecture (x86_64) and runtime (Python 3.9). Click “Create” and we’re done!

From there, we simply attach the Layer to the Lambda Function. A quick test: success!

## Scheduling

To auto-generate the now page content, I set up a scheduler in Amazon EventBridge to invode my Lambda function every 8 hours.

## Acknowledgements

Thanks to [Adam](https://adam.omg.lol) and the entire [omg.lol](https://home.omg.lol) for providing a platform that is full of fun and energy, as well as to [Cory](https://cory.omg.lol) and [Robb](https://robb.omg.lol) who provided the inspiration for this little project.