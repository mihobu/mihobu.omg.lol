---
Date: 2023-02-25 14:49
Tags: Cloud, AWS
Stub: automating-my-now-page-revisited
---

# Automating My Now Page (Revisited)

## What’s Going On Here?

I [recently wrote](/2023/02/automating-my-now-page) about (semi-)automating the generation of my [/now page](https://mihobu.monkeywalk.com/now) using AWS Lambda and easy-to-edit YAML files. I don’t mind adding items to a list by hand, but I didn’t like that the list would keep growing indefinitely. I also felt the entries themselves could be simplified by further automating the timestamp and category somehow.

## Persistent Store

The first change I made was to get the old entries out of the YAML file and into a persistent store. I deceded to use DynamoDB for this. It's super easy to set up and use, and it’s pretty cheap too. Now only new entries need to be entered into the YAML file, and once they’ve been added to the database and to the /now page content, a fresh (empty) YAML file can be dropped back in the pastebin for future updates. The new YAML entries are much simpler too:

```
-
  title: Monocle 24
  icon: microphone
  url: https://monocle.com/radio
```

## Automating the Date

The second change I made was to simply apply the current date at the time of the update rather than entering it manually into the YAML file. Before adding the item records to the DynamoDB table, I add a timestamp plus a serial number (e.g. `2023-02-22-14-00-0001`) in the sort key field. I’m using the same partition key value for all entries. (That might be a problem when I get to hundreds of millions of records, but I’ll risk it for now.) Because the items aren’t timestamped until runtime, my entries may lag by a few hours. I update every three to four hours during the day, so I can live with that.

## Automating the Category

I decided that it was more important to me to display recent items in chronological order, rather than the five most recent items for each category. I’d rather show you that I’ve been watching a lot of TV recently than show you a book I started reading two months ago. And who knows? Maybe it’ll get me to read more. Nah, who am I kidding?

## Color Coding the Items

Since I wouldn’t be displaying the items in groups by category any more, I decided to use CSS to color code the item icons based on the icon name. To do this I added styles for the small handful of icons I’d be using regularly. They will appear in four different colors, for things I'm listening to, reading, watching, and tinkering with. Here’s a sample:

```
i.fa-music, i.fa-headphones { color: hsl(130,50%,50%); }
i.fa-book, i.fa-book-open { color: hsl(220,50%,50%); }
i.fa-tv, i.fa-film { color: hsl(310,50%,50%); }
```

## The Code

The updated Python code for my Lambda function is available [in a paste](https://paste.lol/mihobu/nowbot2.py) if you’re interested.