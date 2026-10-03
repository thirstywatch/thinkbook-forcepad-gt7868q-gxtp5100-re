(function () {
  var rows = document.querySelectorAll("tr.product-row");
  var out = [];
  for (var i = 0; i < rows.length; i++) {
    var n = rows[i].getAttribute("data-product-name");
    if (n === "AW86927AFCR") {
      var a = rows[i].querySelector("a.download-html-link");
      a.click();
      out.push("clicked " + n + " html=" + a.getAttribute("data-html"));
    }
  }
  return out.join(" | ");
})()
