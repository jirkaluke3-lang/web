"""Sestavi webove verze editoru a klientske zony z HTML souboru Apps Scriptu.
Obrazovka bezi na informarchitekti.cz, s Apps Scriptem si vymenuje jen data (doPost ve Web.gs).
Pouziti: python3 sestav.py <Editor.html> <KlientZona.html> <cilova slozka>"""
import sys, re

SERVER = r'''// Na webu (informarchitekti.cz) se aplikace vola jako datova sluzba pres doPost ve Web.gs;
// uvnitr Apps Scriptu pres google.script.run.
var NA_WEBU = !!window.APP_URL && !(window.google && google.script && google.script.run);
function volatSluzbu(fn, args) {
  return fetch(window.APP_URL, { method: 'POST', body: JSON.stringify({ fn: fn, args: args }), credentials: 'omit',
      redirect: 'follow', headers: { 'Content-Type': 'text/plain;charset=utf-8' } })
    .then(function (r) { return r.text(); })
    .then(function (t) {
      var o;
      try { o = JSON.parse(t); } catch (e) {
        var x = new Error('Služba aplikace neodpověděla. Zkuste to za chvíli znovu.'); x.ramec = true; throw x;
      }
      if (o.err) throw new Error(o.err);
      return o.ok;
    }, function () { throw new Error('Bez spojení se službou aplikace. Zkontrolujte připojení k internetu.'); });
}
function server(fn) {
  var args = Array.prototype.slice.call(arguments, 1);
  if (NA_WEBU) return volatSluzbu(fn, args);
  return new Promise(function (res, rej) {
    google.script.run.withSuccessHandler(res).withFailureHandler(function (e) { rej(e); })[fn].apply(null, args);
  });
}'''

def start(token, ramec):
    return ('''function start() { S.token = ss('%s'); if (S.token) zakazky(); else login(); }
// nova sluzba jeste neni nasazena (stary Web.gs bez doPost) -> docasne puvodni zobrazeni v ramu
if (NA_WEBU) volatSluzbu('ping', []).then(start, function (e) { if (e && e.ramec) location.replace('%s'); else { start(); } });
else start();''' % (token, ramec))

def hlava(titul):
    return ('<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            '<title>%s – IN—FORM—ARCHITEKTI</title>\n<meta name="robots" content="noindex">\n'
            '<link rel="icon" href="../favicon.svg">\n<script src="config.js"></script>' % titul)

def uprav(src, titul, token, ramec, vzor_server):
    s = open(src, encoding='utf-8').read().replace('\r\n', '\n')
    assert s.count('<meta charset="utf-8">') == 1
    s = s.replace('<meta charset="utf-8">', hlava(titul))
    m = re.search(vzor_server, s, re.S)
    assert m, 'server() nenalezen v ' + src
    s = s[:m.start()] + SERVER + s[m.end():]
    a = "S.token = ss('%s');\nif (S.token) zakazky(); else login();" % token
    assert s.count(a) == 1, 'start nenalezen v ' + src
    s = s.replace(a, start(token, ramec))
    return s

ed, kz, cil = sys.argv[1:4]
open(cil + '/editor.html', 'w', encoding='utf-8').write(
    uprav(ed, 'Editor zápisů', 'kd_token', 'editor-ram.html', r'function server\(fn\) \{\n.*?\n  \}\);\n\}'))
open(cil + '/zona.html', 'w', encoding='utf-8').write(
    uprav(kz, 'Klientská zóna', 'zona_token', 'zona-ram.html', r'function server\(fn\) \{\n.*?\n\}'))
print('ok')
