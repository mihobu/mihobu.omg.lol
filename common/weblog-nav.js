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
  const navItem = document.querySelectorAll("nav a");
  navItem[2].parentElement.className = "current"; // hard coded the BLOG nav item
}
