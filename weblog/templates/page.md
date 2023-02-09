---
Date: 2023-02-05 16:10
Type: Template
Title: Page Template
---

<!DOCTYPE html>
<html lang="en">

<head>
  <title>{weblog-title}{separator}{post-title}</title>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link href="https://cdn.cache.lol/profiles/themes/css/base.css" rel="stylesheet">
  <link href="https://mihobu.github.io/mihobu.omg.lol/weblog/common/weblog-global.css" rel="stylesheet">
</head>

<body>

  <header>
    <div class="weblog-title"><a href="/"><img src="https://mihobu.github.io/mihobu.omg.lol/weblog/common/mb-roundel.png" />{weblog-title}</a></div>
{navigation}
  </header>

  <main>
    <article>
{body}
    </article>
    <aside class="post-info">
      <i class="fa-solid fa-clock"></i> Last updated: {date}
    </aside>
  </main>

  <footer>
    <p><a href="https://mihobu.monkeywalk.com/">all things mihobu</a> / <a href="https://mihobu.monkeywalk.com/now">now</a></p>
  </footer>

</body>

</html>