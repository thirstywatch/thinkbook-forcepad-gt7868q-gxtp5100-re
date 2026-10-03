JSON.stringify(Array.from(document.querySelectorAll("tr.product-row")).map(function (r) {
  var a = r.querySelector("a.download-file-link");
  return {
    p: r.getAttribute("data-product-name"),
    url: a ? a.getAttribute("data-file-url") : null,
    t: a ? a.getAttribute("data-doc-title") : null
  };
}))
