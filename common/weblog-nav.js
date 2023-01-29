var hc = 0;
const navItems = document.querySelectorAll("nav a");
for (let i = 0; i < navItems.length; i++) {
  var re = new RegExp(navItems[i].innerHTML,"g");
  if ( document.title.match(re) ) {
    navItems[i].parentElement.className = "current";
    hc = hc + 1;
  }
}
if ( hc == 0 ) {
  alert(document.title);
  // no matches were found
  if ( document.title == "404" ) {
    // do nothing
    null;
  }
  else {
    // If no matches were found, highlight the third item ("BLOG")
    const navItem = document.querySelectorAll("nav a");
    navItem[2].parentElement.className = "current";
  }
}
