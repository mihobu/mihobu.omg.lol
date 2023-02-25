---
Date: 2023-02-26 13:04
Type: Template
Title: Gallery Template
---

<!DOCTYPE html>
<html lang="en">

<head>
  <title>{weblog-title}{separator}{post-title}</title>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link href="https://cdn.cache.lol/profiles/themes/css/base.css" rel="stylesheet">
  <link href="https://mihobu.github.io/mihobu.omg.lol/weblog/common/weblog-global.css" rel="stylesheet">
{feeds}
  <style>
div.gallery {
  text-align: center;
}
div.gallery img {
  border: 3px solid;
  border-color: var(--grey-0);
  border-radius: var(--radius);
  max-width: 100%;
  width: 150px;
  height: 120px;
  object-fit: cover;
  box-shadow: 0px 4px 4px rgba(0, 0, 0, 0.25);
  display: inline;
}
div.gallery img:hover {
  cursor: pointer;
  box-shadow: 1px 16px 29px -5px rgba(0, 0, 0, 0.75);
}

.modal {
  display: none;
  position: fixed;
  z-index: 1;
  padding-top: 100px;
  left: 0;
  top: 0;
  width: 100%;
  height: 100%;
  overflow: auto;
  background-color: rgb(0, 0, 0, 0.9);
}

.modal-content {
  margin: auto;
  display: block;
  width: 80%;
  max-width: 700px;
}

.modal-content {
  animation-name: zoom;
  animation-duration: 0.6s;
}

@keyframes zoom {
  from {
    transform: scale(0);
  }
  to {
    transform: scale(1);
  }
}

/* The Close Button */
#close {
  position: absolute;
  top: 15px;
  right: 35px;
  color: #f1f1f1;
  font-size: 40px;
  font-weight: bold;
  transition: 0.3s;
}

#close:hover,
#close:focus {
  color: #bbb;
  text-decoration: none;
  cursor: pointer;
}
  </style>
</head>

<body>

  <header>
    <div class="weblog-title"><a href="/"><img src="https://mihobu.github.io/mihobu.omg.lol/weblog/common/mb-roundel.png" />{weblog-title}</a></div>
{navigation}
  </header>

  <main>
    <article>
{body}
      <aside class="post-info">
        <i class="fa-solid fa-clock"></i> {date}
      </aside>
      <aside class="post-tags">
{tags}
      </aside>
    </article>

    <div>
      <h3>Recent Posts</h3>
{recent-posts}
    </div>

  </main>

  <footer>
    <p><a href="https://mihobu.monkeywalk.com/">all things mihobu</a> / <a href="https://mihobu.monkeywalk.com/now">now</a></p>
  </footer>
<div id="modal" class="modal">
  <span id="close">×</span>
  <img class="modal-content" id="modal-image" />
</div>
</body>

<script>
const modal = document.getElementById("modal");
const images = document.getElementsByClassName("modal-trigger");
const modalImage = document.getElementById("modal-image");

function lightbox(e) {
  modal.style.display = "block";
  modalImage.src = this.src;
  modalImage.alt = this.alt;
}

for (let img of images) {
  img.addEventListener("click", lightbox);
}

const close = document.getElementById("close");
close.addEventListener("click", () => {
  modal.style.display = "none";
});
</script>

</html>