// Column sorting for tables with data-sortable, and drag-and-drop for the upload zone. No external code.
document.querySelectorAll('table[data-sortable]').forEach(function (table) {
  var body = table.tBodies[0];
  table.querySelectorAll('th.sort').forEach(function (th, idx) {
    th.addEventListener('click', function () {
      var col = Array.prototype.indexOf.call(th.parentNode.children, th);
      var dir = th.dataset.dir === 'desc' ? 'asc' : 'desc';
      table.querySelectorAll('th.sort').forEach(function (o) { delete o.dataset.dir; });
      th.dataset.dir = dir;
      var rows = Array.prototype.slice.call(body.rows);
      rows.sort(function (a, b) {
        var av = a.cells[col].dataset.v, bv = b.cells[col].dataset.v;
        var an = parseFloat(av), bn = parseFloat(bv);
        var cmp = (isNaN(an) || isNaN(bn)) ? String(av).localeCompare(String(bv), 'pt') : an - bn;
        return dir === 'desc' ? -cmp : cmp;
      });
      rows.forEach(function (r) { body.appendChild(r); });
    });
  });
});
var dz = document.getElementById('dropzone');
if (dz) {
  var input = dz.querySelector('input[type=file]');
  var label = document.getElementById('picked');
  var show = function () { label.textContent = input.files.length ? input.files.length + ' ficheiro(s) selecionado(s)' : ''; };
  ['dragenter', 'dragover'].forEach(function (ev) { dz.addEventListener(ev, function (e) { e.preventDefault(); dz.classList.add('over'); }); });
  ['dragleave', 'drop'].forEach(function (ev) { dz.addEventListener(ev, function () { dz.classList.remove('over'); }); });
  dz.addEventListener('drop', function (e) { e.preventDefault(); input.files = e.dataTransfer.files; show(); });
  input.addEventListener('change', show);
}
