// Wrap the header site title in a link to the site root. Material's
// default markup leaves the title as plain text; only the small logo
// icon to the left is clickable. Wrapping it as an <a> matches the
// behavior most readers expect.
document$.subscribe(function () {
  var topic = document.querySelector(".md-header__title .md-ellipsis");
  if (!topic || topic.querySelector("a")) return;
  var logo = document.querySelector(".md-header__button.md-logo");
  var href = (logo && logo.getAttribute("href")) || ".";
  var text = topic.textContent.trim();
  var link = document.createElement("a");
  link.href = href;
  link.textContent = text;
  link.className = "md-header__title-link";
  topic.innerHTML = "";
  topic.appendChild(link);
});
