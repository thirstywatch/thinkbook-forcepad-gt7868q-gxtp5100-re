(function () {
  var h = String(document.documentElement.outerHTML);
  var i = h.indexOf("AW86927AFCR");
  if (i < 0) return "notfound";
  return h.slice(i - 400, i + 2000).replace(/\s+/g, " ");
})()
