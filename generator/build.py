#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IN—FORM—ARCHITEKTI — generátor statického webu.

Čte data z CSV (data/*.csv — export z Google Sheetu) a obrazy ze složek
(obrazky/…), generuje hotový web do složky site/.

Spuštění:  python3 generator/build.py
Vše ostatní (CSS, fonty, chování) je zabudováno zde a v šabloně.
"""

import csv, os, html, shutil, re, json, urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
IMG  = ROOT / "obrazky"
OUT  = ROOT / "site"

# ------- konfigurace webu -------
DOMENA   = "https://informarchitekti.cz"      # kanonická adresa
IMG_EXT  = (".jpg", ".jpeg", ".jfif", ".png", ".webp", ".avif", ".mp4", ".webm", ".gif")
VIDEO_EXT= (".mp4", ".webm")

# ---------------------------------------------------------------------------
# načtení dat
# ---------------------------------------------------------------------------
def read_csv(name):
    path = DATA / f"{name}.csv"
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig") as f:   # utf-8-sig = odstraní BOM z Googlu
        rows = list(csv.DictReader(f))
    # normalizace klíčů: ořez mezer a BOM, sjednocení
    clean = []
    for r in rows:
        clean.append({(k or "").strip().lstrip("\ufeff"): (v if v is not None else "")
                      for k, v in r.items()})
    print(f"  [data] {name}.csv: {len(clean)} řádků, sloupce: {list(clean[0].keys()) if clean else '—'}")
    return clean

def truthy(v):
    return str(v).strip().upper() in ("ANO", "YES", "1", "TRUE", "X")

def load_projects(csvname, folder):
    rows = read_csv(csvname)
    out = []
    for r in rows:
        if not r.get("slug"): continue
        if r.get("publikovat") and not truthy(r["publikovat"]): continue
        slug = r["slug"].strip()
        out.append({
            "slug": slug,
            "nazev": (r.get("nazev_cz") or "").strip(),
            "lokalita": (r.get("lokalita") or "").strip(),
            "rok": (r.get("rok") or "").strip().replace(".0",""),
            "typ": (r.get("typ") or "").strip(),
            "faze": (r.get("faze") or "").strip(),
            "charakter": (r.get("charakter") or "").strip(),
            "anotace": (r.get("anotace_cz") or "").strip(),
            "seo": (r.get("seo_popis_cz") or "").strip(),
            "slozka": (r.get("slozka_obrazu") or slug).strip(),
            "foto": (r.get("autor_fotografii") or "").strip(),
            "poradi": r.get("poradi") or "999",
            "images": gather_images(folder, (r.get("slozka_obrazu") or slug).strip()),
        })
    out.sort(key=lambda p: (int(re.sub(r"\D","",p["poradi"]) or 999)))
    return out

def gather_images(folder, slozka):
    """Seznam obrazů ve složce projektu + popisky z popisky.txt."""
    d = IMG / folder / slozka
    captions, weaves = parse_popisky(d / "popisky.txt")
    files = []
    if d.exists():
        for fn in sorted(os.listdir(d)):
            if fn.lower().endswith(IMG_EXT):
                num = re.sub(r"\D", "", os.path.splitext(fn)[0])[:2] or None
                files.append({"file": fn, "num": num,
                              "video": fn.lower().endswith(VIDEO_EXT),
                              "cap": captions.get(num, "")})
    # fallback: nejsou-li fyzické soubory, vytvoř 3 placeholdery, ať web žije
    if not files:
        for i in range(1, 4):
            n = f"{i:02d}"
            files.append({"file": None, "num": n, "video": False, "cap": captions.get(n, "")})
    return {"files": files, "weaves": weaves}

def parse_popisky(path):
    """[01] -> první řádek = hlavička (caption/alt), zbytek = vpletený text."""
    captions, weaves = {}, {}
    if not path.exists():
        return captions, weaves
    blocks = re.split(r"\n(?=\[\d+\])", path.read_text(encoding="utf-8").strip())
    for b in blocks:
        m = re.match(r"\[(\d+)\]\s*(.*)", b, re.S)
        if not m: continue
        num = m.group(1)
        body = [l.rstrip() for l in m.group(2).splitlines() if l.strip()]
        if body:
            captions[num] = body[0]
            if len(body) > 1:
                weaves[num] = " ".join(body[1:])
    return captions, weaves

def load_news(rows):
    """Inkubátor v novinkové podobě (datum/stitek/titulek/text/obraz/projekt_slug)."""
    out = []
    for r in rows:
        if r.get("publikovat") and not truthy(r["publikovat"]): continue
        tit = (r.get("titulek_cz") or "").strip()
        if not tit and not (r.get("text_cz") or "").strip(): continue
        out.append({
            "datum": (r.get("datum") or "").strip(),
            "stitek": (r.get("stitek") or "").strip(),
            "titulek": tit,
            "text": (r.get("text_cz") or "").strip(),
            "obraz": (r.get("obraz") or "").strip(),
            "projekt": (r.get("projekt_slug") or "").strip(),
        })
    return out


def load_settings():
    return {r["klic"]: (r.get("hodnota_cz") or "").strip()
            for r in read_csv("nastaveni") if r.get("klic")}

def filename_parts(fn):
    """Název souboru bez přípony rozdělený podle '_' na řádky, přesně v té
    velikosti písmen, v jaké je pojmenovaný soubor (žádné vynucené malé/velké).
    Jiné znaky (pomlčky, mezery, čísla, diakritika) se v rámci řádku nemění."""
    stem = os.path.splitext(fn)[0]
    return [part for part in stem.split("_") if part]

def load_backgrounds():
    # titulky z listu POZADI, klíčované názvem souboru (volitelné)
    caps = {}
    for r in read_csv("pozadi"):
        f = (r.get("soubor") or "").strip()
        if f:
            caps[os.path.basename(f)] = (r.get("titulek_cz") or "").strip()
    # pozadí = vše, co je fyzicky ve složce obrazky/pozadi
    d = IMG / "pozadi"
    out = []
    if d.exists():
        for fn in sorted(os.listdir(d)):
            if fn.lower().endswith(IMG_EXT):
                is_video = fn.lower().endswith(VIDEO_EXT)
                out.append({"file": f"pozadi/{fn}", "cap": caps.get(fn, ""),
                            "video": is_video,
                            # u videí se název na střed nezobrazuje (viz page_vstup)
                            "name_parts": [] if is_video else filename_parts(fn)})
    print(f"  [pozadi] {len(out)} souborů použito jako pozadí")
    return out

# ---------------------------------------------------------------------------
# stavební kameny šablony
# ---------------------------------------------------------------------------
def e(s): return html.escape(s or "", quote=True)

CSS = (ROOT / "generator" / "styl.css").read_text(encoding="utf-8")

def head(title, desc, canonical, depth, jsonld=None):
    root = "../" * depth
    ld = f'\n<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>' if jsonld else ""
    return f"""<!DOCTYPE html>
<html lang="cs">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:type" content="website">
<meta name="theme-color" content="#0a0a0a">
<link rel="icon" type="image/svg+xml" href="{root}favicon.svg">
<link rel="preload" as="font" type="font/woff" href="{root}fonty/Ciutadella-Regular.woff" crossorigin>
<link rel="stylesheet" href="{root}fonty/fonty.css">
<style>{CSS}</style>{ld}
</head>
<body>"""

FOOT = "\n</body>\n</html>\n"

def bar(active, depth):
    root = "../" * depth
    items = [("projekty","PROJEKTY","projekty/"),
             ("kontakt","KONTAKT","kontakt/")]
    links = "".join(
        f'<a href="{root}{href}" class="{"act" if k==active else ""}">{lbl}</a>'
        for k,lbl,href in items)
    return f"""<header class="bar meta">
  <a class="home display" href="{root}">IN—FORM—ARCHITEKTI</a>
  <nav>{links}</nav>
</header>"""

def ph(kind, cls, num=None, src=None, root=""):
    """Obraz nebo placeholder. src=None -> šedý placeholder s číslem."""
    inner = f'<div class="inner">{e(num or "")}</div>'
    if src:
        if src.lower().endswith(VIDEO_EXT):
            return f'<div class="ph {cls}"><video class="media" src="{root}{src}" autoplay muted loop playsinline></video></div>'
        return f'<div class="ph {cls}"><img class="media" loading="lazy" src="{root}{src}" alt="{e(kind)}"></div>'
    return f'<div class="ph {cls}">{inner}</div>'

# ---------------------------------------------------------------------------
# galerie + detail projektu (rytmus obrazů + vpletené texty)
# ---------------------------------------------------------------------------
RATIOS = ["r43", "r34", "r34", "r43", "r32", "r34"]

def gallery_html(p, root):
    imgs = p["images"]["files"]
    weaves = p["images"]["weaves"]
    parts = []
    used_weaves = set()
    for i, im in enumerate(imgs):
        ratio = "r43" if i == 0 else RATIOS[i % len(RATIOS)]
        wide = ' class="wide"' if (i == 0 or ratio == "r32") else ""
        src = f'obrazky/{p["_folder"]}/{p["slozka"]}/{im["file"]}' if im["file"] else None
        cap = f'<figcaption>{e(im["cap"])}</figcaption>' if im["cap"] else ""
        parts.append(f'<figure{wide}>{ph(im["cap"], ratio, im["num"], src, root)}{cap}</figure>')
        # vpletený text po obrazu, k jehož číslu patří
        if im["num"] in weaves and im["num"] not in used_weaves:
            used_weaves.add(im["num"])
            parts.append(f'<div class="weave"><p class="body-t">{e(weaves[im["num"]])}</p></div>')
    # vpletené texty bez odpovídajícího obrazu doplň na konec
    for num, txt in weaves.items():
        if num not in used_weaves:
            parts.append(f'<div class="weave"><p class="body-t">{e(txt)}</p></div>')
    return '<div class="gal">' + "".join(parts) + "</div>"

def detail_block(p, root, is_ink=False):
    eyebrow = '<p class="meta ink-eyebrow">INKUBÁTOR</p>' if is_ink else ""
    params = [("Místo", p["lokalita"]), ("Typ", p["typ"]), ("Fáze", p["faze"]),
              ("Charakter", p["charakter"]), ("Rok", p["rok"]), ("Foto", p["foto"])]
    phtml = "".join(f'<div><div class="k">{e(k)}</div><div>{e(v)}</div></div>'
                    for k, v in params if v)
    return f"""<article class="proj" id="proj-{e(p['slug'])}">
  {eyebrow}<div class="detail-head"><h2 class="h-page display">{e(p['nazev'])}</h2></div>
  <div class="params meta">{phtml}</div>
  <p class="body-t">{e(p['anotace'])}</p>
  {gallery_html(p, root)}
</article>"""

def jsonld_project(p):
    return {"@context":"https://schema.org","@type":"CreativeWork",
            "name":p["nazev"],"creator":{"@type":"Organization","name":"IN—FORM—ARCHITEKTI"},
            "locationCreated":p["lokalita"],"dateCreated":p["rok"],
            "description":p["seo"] or p["anotace"][:155]}

# ---------------------------------------------------------------------------
# stránky
# ---------------------------------------------------------------------------
def write(path_parts, content):
    out = OUT.joinpath(*path_parts)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")

def page_vstup(cfg, backs):
    name = cfg.get("nazev_atelieru", "IN—FORM—ARCHITEKTI")
    intro = cfg.get("uvodni_text", "")
    data = [{"src": (b["file"] if b["file"].startswith("http") else urllib.parse.quote(f'obrazky/{b["file"]}', safe="/")),
             "cap": b["cap"], "video": b["video"], "parts": b["name_parts"]} for b in backs]
    parts = name.split("\u2014")
    brand = ('IN<span class="dash">\u2014</span>FORM<span class="dash2">\u2014</span>ARCHITEKTI'
             if len(parts) == 3 else e(name))
    intro_html = f'<p class="intro body-t">{e(intro)}</p>' if intro else ""
    return head(name, cfg.get("medailon","")[:155], DOMENA+"/", 0) + f"""
<section id="vstup" title="Klikněte pro další obraz">
  <div class="bg" id="bg"></div>
  <a class="brand display" href="projekty/" id="brandLink">{brand}</a>
  {intro_html}
  <p class="filename display" id="fname"></p>
  <p class="caption meta" id="cap"></p>
</section>
<script>
const B={json.dumps(data, ensure_ascii=False)};
let i = B.length ? Math.floor(Math.random()*B.length) : -1;
const vstup=document.getElementById('vstup'), bg=document.getElementById('bg'), cap=document.getElementById('cap'), fname=document.getElementById('fname');
const TYPE_MS=90, PRE_PAUSE_MS=5000, HOLD_MS=2000;
let seq=0;
function fallback(){{bg.style.backgroundImage='';bg.style.background='linear-gradient(160deg,#3d3d3d,#141414)';bg.innerHTML='';}}
// barva VEŠKERÉHO textu na titulní straně (logo, středový text, popisek...) se řídí
// jasem právě zobrazeného obrazu: světlá #F7F7F7 na tmavém obraze, tmavá #4A4A4A na
// světlém. Nastavuje se na celou sekci #vstup, aby se všechny texty přepnuly společně.
function pickTextColor(img){{
  try{{
    var cw=32, ch=32;
    var c=document.createElement('canvas'); c.width=cw; c.height=ch;
    var ctx=c.getContext('2d');
    var iw=img.naturalWidth||img.width, ih=img.naturalHeight||img.height;
    var cropW=iw*0.6, cropH=ih*0.6, sx=(iw-cropW)/2, sy=(ih-cropH)/2;
    ctx.drawImage(img, sx, sy, cropW, cropH, 0, 0, cw, ch);
    var d=ctx.getImageData(0,0,cw,ch).data, sum=0, n=0;
    for(var k=0;k<d.length;k+=4){{ sum+=0.2126*d[k]+0.7152*d[k+1]+0.0722*d[k+2]; n++; }}
    vstup.style.color = (sum/n) > 175 ? '#4A4A4A' : '#F7F7F7';
  }}catch(e){{ vstup.style.color = '#F7F7F7'; }}
}}
// psací stroj: pro každý zobrazený obraz zvlášť. Přepnutí na jiný obraz (klik i nové
// načtení) okamžitě zruší běžící sekvenci a smaže text; pro nový obraz jede pravidlo znovu:
// 5 s pauza -> napsání po písmenech -> 2 s pauza -> smazání najednou.
function typeParts(parts, wi, ci, mySeq, done, span){{
  if(mySeq!==seq) return;               // mezitím se přepnul obraz - přestat
  if(wi>=parts.length){{done();return;}}
  const word=parts[wi];
  if(ci===0){{
    // každý úsek (mezi "_") dostane vlastní nedělitelný blok - zalomit řádek
    // smí jedině naše <br>, nikdy mezera/pomlčka uvnitř úseku
    if(wi>0) fname.appendChild(document.createElement('br'));
    span=document.createElement('span');
    span.className='w';
    fname.appendChild(span);
  }}
  if(ci<word.length){{
    span.appendChild(document.createTextNode(word[ci]));
    setTimeout(function(){{typeParts(parts,wi,ci+1,mySeq,done,span);}}, TYPE_MS);
  }} else {{
    typeParts(parts,wi+1,0,mySeq,done,span);
  }}
}}
function scheduleTyping(p, mySeq){{
  if(p.video || !p.parts || !p.parts.length) return;
  setTimeout(function(){{
    if(mySeq!==seq) return;
    typeParts(p.parts, 0, 0, mySeq, function(){{
      if(mySeq!==seq) return;
      setTimeout(function(){{ if(mySeq===seq) fname.textContent=''; }}, HOLD_MS);
    }});
  }}, PRE_PAUSE_MS);
}}
function show(){{
  const mySeq=++seq;
  fname.textContent='';                 // okamžitý reset při každém přepnutí/načtení
  vstup.style.color='#F7F7F7';          // výchozí, dokud se nezjistí jas nového obrazu
  if(i<0){{fallback();cap.textContent='';return;}}
  const p=B[i];
  if(p.video){{bg.style.background='#141414';bg.innerHTML='';var v=document.createElement('video');v.className='media';v.src=p.src;v.autoplay=v.muted=v.loop=v.playsInline=true;v.onerror=fallback;bg.appendChild(v);scheduleTyping(p,mySeq);}}
  else{{fallback();var im=new Image();im.onload=function(){{bg.innerHTML='';bg.style.backgroundImage='url('+p.src+')';bg.style.backgroundSize='cover';bg.style.backgroundPosition='center';pickTextColor(im);scheduleTyping(p,mySeq);}};im.onerror=function(){{fallback();scheduleTyping(p,mySeq);}};im.src=p.src;}}
  cap.textContent=p.cap||'';
}}
show();
document.getElementById('vstup').addEventListener('click',function(ev){{
  if(ev.target.closest('#brandLink')) return;
  if(B.length>1){{ i=(i+1)%B.length; show(); }}
}});
</script>""" + FOOT

def page_rozcestnik(cfg):
    return head("IN—FORM—ARCHITEKTI", cfg.get("medailon","")[:155], DOMENA+"/rozcestnik/", 1) + f"""
<section id="rozcestnik">
  <a class="brand-s display" href="../">IN—FORM—ARCHITEKTI</a>
  <nav>
    <a class="display" href="../onas/"><span class="pre">—</span>O NÁS</a>
    <a class="display" href="../projekty/"><span class="pre">—</span>PROJEKTY</a>
    <a class="display" href="../kontakt/"><span class="pre">—</span>KONTAKT</a>
  </nav>
  <div class="foot meta"><span>Praha</span><span>50.0755 N · 14.4378 E</span></div>
</section>""" + FOOT

def card(p, root, base):
    ratio = "r43"
    im = p["images"]["files"][0]
    src = f'obrazky/{p["_folder"]}/{p["slozka"]}/{im["file"]}' if im["file"] else None
    tag = " · ".join(x for x in (p["typ"], p["faze"], p["charakter"]) if x)
    loc = " · ".join(x for x in (p["lokalita"], p["rok"]) if x)
    return f"""<a class="card" href="{root}{base}/{e(p['slug'])}/">
  {ph(p['nazev'], ratio, im['num'], src, root)}
  <p class="tag meta">{e(tag)}</p>
  <h3 class="display">{e(p['nazev'])}</h3>
  <p class="loc meta">{e(loc)}</p>
  <p class="txt body-t">{e(p['anotace'][:180])}</p>
</a>"""

def page_projekty(cfg, projekty):
    medailon = cfg.get("medailon", "")
    cards = "".join(card(p, "../", "projekty") for p in projekty)
    med = f"""<div class="medailon">
      {ph("Ateliér","r34", None, ("../obrazky/"+cfg['medailon_foto']) if (cfg.get('medailon_foto') and (IMG/cfg['medailon_foto']).exists()) else None, "")}
      <div class="txt"><h2 class="h-page display">Ateliér</h2><p class="body-t">{e(medailon)}</p></div>
    </div>""" if medailon else ""
    body = f"""{bar("projekty",1)}
<div class="page">
  {med}
  <div class="grid">{cards}</div>
</div>"""
    return head("Projekty — IN—FORM—ARCHITEKTI",
                "Realizace, projekty a studie ateliéru IN—FORM—ARCHITEKTI.",
                DOMENA+"/projekty/", 1) + body + FOOT

def page_stream(item, projekty, inkubator, group):
    """Detail: rozkliknutý první, pak zbytek skupiny (rotace), pak druhá skupina."""
    root = "../../"
    if group == "i":
        idx = [x["slug"] for x in inkubator].index(item["slug"])
        order = [(x, True) for x in inkubator[idx:] + inkubator[:idx]] + [(x, False) for x in projekty]
        back = ("../../inkubator/", "← zpět na inkubátor")
    else:
        idx = [x["slug"] for x in projekty].index(item["slug"])
        order = [(x, False) for x in projekty[idx:] + projekty[:idx]] + [(x, True) for x in inkubator]
        back = ("../../projekty/", "← všechny projekty")
    blocks = '<hr class="proj-sep">'.join(detail_block(x, root, is_ink) for x, is_ink in order)
    body = f"""{bar("inkubator" if group=="i" else "projekty",2)}
<div class="page">
  <a class="back meta" href="{back[0]}">{back[1]}</a>
  {blocks}
</div>"""
    title = f'{item["nazev"]} — IN—FORM—ARCHITEKTI'
    desc = item["seo"] or item["anotace"][:155]
    canon = f'{DOMENA}/{"inkubator" if group=="i" else "projekty"}/{item["slug"]}/'
    return head(title, desc, canon, 2, jsonld_project(item)) + body + FOOT

def news_feed_html(items, root):
    arts = []
    for n in items:
        has_img = n["obraz"] and (IMG / n["obraz"]).exists()
        img = ph(n["titulek"], "r43", None, (n["obraz"] if has_img else None), root)
        tag = f'<p class="tag meta" style="margin-top:14px">{e(n["stitek"])}</p>' if n["stitek"] else ""
        date = f'<p class="date meta">{e(n["datum"])}</p>' if n["datum"] else ""
        link = (f'<p style="margin-top:10px"><a class="body-t" href="{root}projekty/{e(n["projekt"])}/">Projekt →</a></p>'
                if n["projekt"] else "")
        arts.append(f'<article>{img}{tag}<h3 class="display">{e(n["titulek"])}</h3>{date}'
                    f'<p class="body-t">{e(n["text"])}</p>{link}</article>')
    return '<div class="news">' + "".join(arts) + '</div>'


def page_inkubator(cfg, inkubator, inkubator_news):
    intro = '<p class="body-t intro-block">Rozpracované, experimentální a výzkumné práce ateliéru — prototypy, materiálové zkoušky, soutěžní návrhy.</p>'
    if inkubator:                       # projektová podoba listu
        inner = '<div class="grid">' + "".join(card(p, "../", "inkubator") for p in inkubator) + '</div>'
    else:                               # novinková podoba listu
        inner = news_feed_html(inkubator_news, "../")
    body = f"""{bar("inkubator",1)}
<div class="page">
  <h2 class="h-page display">Inkubátor</h2>
  {intro}
  {inner}
</div>"""
    return head("Inkubátor — IN—FORM—ARCHITEKTI",
                "Rozpracované a experimentální práce ateliéru IN—FORM—ARCHITEKTI.",
                DOMENA+"/inkubator/", 1) + body + FOOT

def page_text(cfg, active, title, key, fallback=""):
    txt = cfg.get(key, fallback)
    paras = "".join(f"<p>{e(l)}</p>" for l in txt.split("\n") if l.strip())
    body = f"""{bar(active,1)}
<div class="page"><h2 class="h-page display">{e(title)}</h2><div class="stack body-t">{paras}</div></div>"""
    return head(f"{title} — IN—FORM—ARCHITEKTI", txt[:155] or title, f"{DOMENA}/{active}/", 1) + body + FOOT

def page_kontakt(cfg):
    adr = cfg.get("kontakt_adresa","").replace("\n","<br>")
    email = cfg.get("kontakt_email",""); tel = cfg.get("kontakt_telefon","")
    ic = cfg.get("kontakt_ic",""); ig = cfg.get("instagram","")
    body = f"""{bar("kontakt",1)}
<div class="page"><h2 class="h-page display">Kontakt</h2>
<div class="stack body-t">
  <p>{adr}</p>
  <p class="email-line" style="margin-top:12px">E-mail: <a href="mailto:{e(email)}">{e(email)}</a></p>
  {f'<p style="margin-top:6px">Telefon: {e(tel)}</p>' if tel else ''}
  {f'<p style="margin-top:6px">{e(ic)}</p>' if ic else ''}
  {f'<p style="margin-top:12px"><a href="{e(ig)}">Instagram</a></p>' if ig else ''}
</div></div>"""
    return head("Kontakt — IN—FORM—ARCHITEKTI", "Kontakt na ateliér IN—FORM—ARCHITEKTI.",
                DOMENA+"/kontakt/", 1) + body + FOOT

def sitemap(projekty, inkubator):
    urls = ["/", "/projekty/", "/inkubator/", "/onas/", "/kontakt/", "/jobs/"]
    urls += [f"/projekty/{p['slug']}/" for p in projekty]
    urls += [f"/inkubator/{p['slug']}/" for p in inkubator]
    body = "".join(f"<url><loc>{DOMENA}{u}</loc></url>" for u in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>'

# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------
def main():
    if OUT.exists(): shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    cfg = load_settings()
    projekty = load_projects("projekty", "projekty")
    for p in projekty:  p["_folder"] = "projekty"

    ink_rows = read_csv("inkubator")
    ink_project_mode = bool(ink_rows) and ("slug" in ink_rows[0])
    if ink_project_mode:
        inkubator = load_projects("inkubator", "inkubator")
        for p in inkubator: p["_folder"] = "inkubator"
        inkubator_news = []
        print(f"  [inkubator] projektový režim: {len(inkubator)} položek")
    else:
        inkubator = []
        inkubator_news = load_news(ink_rows)
        print(f"  [inkubator] novinkový režim: {len(inkubator_news)} položek")
    backs = load_backgrounds()

    write(["index.html"], page_vstup(cfg, backs))
    write(["projekty","index.html"], page_projekty(cfg, projekty))
    write(["inkubator","index.html"], page_inkubator(cfg, inkubator, inkubator_news))
    for p in projekty:
        write(["projekty", p["slug"], "index.html"], page_stream(p, projekty, inkubator, "p"))
    for p in inkubator:
        write(["inkubator", p["slug"], "index.html"], page_stream(p, projekty, inkubator, "i"))
    write(["onas","index.html"], page_text(cfg, "onas", "O nás", "onas_text",
          "Text o ateliéru doplňte v listu NASTAVENÍ (onas_text)."))
    write(["jobs","index.html"], page_text(cfg, "jobs", "Jobs", "jobs_text",
          "V tuto chvíli nenabíráme."))
    write(["kontakt","index.html"], page_kontakt(cfg))

    # kopie statiky
    shutil.copytree(ROOT / "fonty", OUT / "fonty")
    if IMG.exists(): shutil.copytree(IMG, OUT / "obrazky", dirs_exist_ok=True)
    write(["sitemap.xml"], sitemap(projekty, inkubator))
    write(["robots.txt"], f"User-agent: *\nAllow: /\nSitemap: {DOMENA}/sitemap.xml\n")
    (OUT / ".nojekyll").write_text("")
    # favicon: signálně žlutý čtverec (barvu lze změnit níže)
    (OUT / "favicon.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
        '<rect width="32" height="32" fill="#FFD400"/></svg>')
    # vlastní doména
    (OUT / "CNAME").write_text("informarchitekti.cz\n")

    print(f"Hotovo: {len(projekty)} projektů, {len(inkubator)} inkubátor. Web ve složce site/.")

if __name__ == "__main__":
    main()
