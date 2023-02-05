---
Date: 2023-02-05 16:13
Type: Template
Title: Archive Template
---

<!DOCTYPE html>
<html lang="en">

<head>
  <title>{weblog-title}{separator}{post-title}</title>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
@import url("https://mihobu.github.io/mihobu.omg.lol/weblog/common/weblog-global.css");
  </style>
{feeds}
</head>

<body>

  <header>
    <div id="roundel"><img src="https://mihobu.github.io/mihobu.omg.lol/weblog/common/mb-roundel.png" height="100"/></div>
    <nav class="navbar">
      <ul class="nav-links">
        <input type="checkbox" id="checkbox_toggle" />
        <label for="checkbox_toggle" class="hamburger">☰</label>
        <!-- NAVIGATION MENUS -->
        <div class="menu">
          <li><a href="/">Latest</a></li>
          <li><a href="/archive">Archive</a></li>
          <li><a href="/downloads">Downloads</a></li>
          <li><a href="/about">About Me</a></li>
        </div>
      </ul>
    </nav>
  </header>

  <main>
{body}
  </div></main>

  <footer>
    <p><a href="https://mihobu.monkeywalk.com/">all things mihobu</a> / <a href="https://mihobu.monkeywalk.com/now">now</a></p>
  </footer>

</body>
<script>
var hc = 0;
const navItems = document.querySelectorAll("nav a");
loc = window.location.href.toString().split(window.location.host)[1];
if ( loc == "/" ) { navItems[0].parentElement.className = "current"; }
else if ( loc == "/archive" ) { navItems[1].parentElement.className = "current"; }
else if ( loc == "/downloads" ) { navItems[2].parentElement.className = "current"; }
else if ( loc == "/about" ) { navItems[3].parentElement.className = "current"; }
</script>
</html>