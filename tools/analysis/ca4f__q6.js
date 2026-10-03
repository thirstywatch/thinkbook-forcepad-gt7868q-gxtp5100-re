(function () {
  var t = document.body.innerText.replace(/[ \t]+/g, " ");
  var lines = t.split("\n");
  var want = [];
  for (var i = 0; i < lines.length; i++) {
    if (/丝印|marking|Marking|封装|型号/.test(lines[i])) {
      want.push(lines[i].trim());
    }
  }
  return document.title + "\n---\n" + want.slice(0, 40).join("\n");
})()
