JSON.stringify(Array.from(document.querySelectorAll("table tr")).map(function (r) {
  var a = r.querySelector("a[href*='.pdf']");
  return a ? (r.innerText.replace(/\s+/g, " ").trim().slice(0, 16) + " => " + a.href) : null;
}).filter(Boolean))
