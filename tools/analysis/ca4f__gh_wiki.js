(function () {
  var el = document.querySelector(".markdown-body") || document.querySelector("article") || document.body;
  var t = el.innerText.replace(/\n{3,}/g, "\n\n");
  return t.slice(0, 6000);
})()
