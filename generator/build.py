#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IN—FORM—ARCHITEKTI — generátor statického webu.

Čte data z CSV (data/*.csv — export z Google Sheetu) a obrazy ze složek
(obrazky/…), generuje hotový web do složky site/.

Spuštění:  python3 generator/build.py
Vše ostatní (CSS, fonty, chování) je zabudováno zde a v šabloně.
"""

import csv, os, html, shutil, re, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
IMG  = ROOT / "obrazky"
OUT  = ROOT / "site"

# ------- konfigurace webu -------
DOMENA   = "https://informarchitekti.cz"      # kanonická adresa
IMG_EXT  = (".jpg", ".jpeg", ".png", ".webp", ".avif", ".mp4", ".webm", ".gif")
VIDEO_EXT= (".mp4", ".webm")

# ---------------------------------------------------------------------------
# načtení dat
# ---------------------------------------------------------------------------
def read_csv(name):
    path = DATA / f"{name}.csv"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))

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
            "rok": (r.get("rok") or "").strip(),
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

def load_settings():
    return {r["klic"]: (r.get("hodnota_cz") or "").strip()
            for r in read_csv("nastaveni") if r.get("klic")}

def load_backgrounds():
    rows = read_csv("pozadi")
    out = []
    for r in rows:
        if r.get("aktivni") and not truthy(r["aktivni"]): continue
        f = (r.get("soubor") or "").strip()
        if not f: continue
        out.append({"file": f, "cap": (r.get("titulek_cz") or "").strip(),
                    "video": f.lower().endswith(VIDEO_EXT)})
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
<link rel="preload" as="font" type="font/woff" href="{root}fonty/Ciutadella-Regular.woff" crossorigin>
<link rel="stylesheet" href="{root}fonty/fonty.css">
<style>{CSS}</style>{ld}
</head>
<body>"""

FOOT = "\n</body>\n</html>\n"

def bar(active, depth):
    root = "../" * depth
    items = [("projekty","PROJEKTY","projekty/"),
             ("onas","O NÁS","onas/"),
             ("inkubator","INKUBÁTOR","inkubator/"),
             ("kontakt","KONTAKT","kontakt/"),
             ("jobs","JOBS","jobs/")]
    links = "".join(
        f'<a href="{root}{href}" class="{"act" if k==active else ""}">{lbl}</a>'
        for k,lbl,href in items)
    return f"""<header class="bar meta">
  <a class="home display" href="{root}rozcestnik/">IN—FORM—ARCHITEKTI</a>
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
    data = [{"src": (f'obrazky/pozadi/{b["file"]}' if not b["file"].startswith("http") else b["file"]),
             "cap": b["cap"], "video": b["video"]} for b in backs]
    # placeholder, nejsou-li pozadí
    if not data:
        data = [{"src": None, "cap": "", "video": False}]
    parts = name.split("—")
    brand = ("IN<span class=\"dash\">—</span>FORM<span class=\"dash2\">—</span>ARCHITEKTI"
             if len(parts) == 3 else e(name))
    intro_html = f'<p class="intro body-t">{e(intro)}</p>' if intro else ""
    return head(name, cfg.get("medailon","")[:155], DOMENA+"/", 0) + f"""
<section id="vstup" onclick="location.href='rozcestnik/'" title="Vstoupit">
  <div class="bg" id="bg"></div>
  <h1 class="brand display">{brand}</h1>
  {intro_html}
  <p class="caption meta" id="cap"></p>
  <p class="enter meta">vstoupit <span>→</span></p>
</section>
<script>
const B={json.dumps(data, ensure_ascii=False)};
const p=B[Math.floor(Math.random()*B.length)];
const bg=document.getElementById('bg');
if(p.src && p.video){{bg.innerHTML='<video class="media" src="'+p.src+'" autoplay muted loop playsinline></video>';}}
else if(p.src){{bg.style.backgroundImage='url('+p.src+')';bg.style.backgroundSize='cover';bg.style.backgroundPosition='center';}}
else{{bg.style.background='linear-gradient(160deg,#3d3d3d,#141414)';bg.innerHTML='<div class="ph-label">POZADÍ<br>(list POZADÍ + složka obrazky/pozadi)</div>';}}
document.getElementById('cap').textContent=p.cap||'';
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
    src = f'{root}obrazky/{p["_folder"]}/{p["slozka"]}/{im["file"]}' if im["file"] else None
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
      {ph("Ateliér","r34", None, ("../"+ 'obrazky/'+cfg['medailon_foto']) if cfg.get('medailon_foto') else None, "")}
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

def page_inkubator(cfg, inkubator):
    cards = "".join(card(p, "../", "inkubator") for p in inkubator)
    intro = '<p class="body-t intro-block">Rozpracované, experimentální a výzkumné práce ateliéru — prototypy, materiálové zkoušky, soutěžní návrhy.</p>'
    body = f"""{bar("inkubator",1)}
<div class="page">
  <h2 class="h-page display">Inkubátor</h2>
  {intro}
  <div class="grid">{cards}</div>
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
  <p style="margin-top:12px">E-mail: <a href="mailto:{e(email)}">{e(email)}</a>{f'<br>Telefon: {e(tel)}' if tel else ''}{f'<br>{e(ic)}' if ic else ''}</p>
  {f'<p style="margin-top:12px"><a href="{e(ig)}">Instagram</a></p>' if ig else ''}
</div></div>"""
    return head("Kontakt — IN—FORM—ARCHITEKTI", "Kontakt na ateliér IN—FORM—ARCHITEKTI.",
                DOMENA+"/kontakt/", 1) + body + FOOT

def sitemap(projekty, inkubator):
    urls = ["/", "/rozcestnik/", "/projekty/", "/inkubator/", "/onas/", "/kontakt/", "/jobs/"]
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
    inkubator = load_projects("inkubator", "inkubator")
    for p in projekty:  p["_folder"] = "projekty"
    for p in inkubator: p["_folder"] = "inkubator"
    backs = load_backgrounds()

    write(["index.html"], page_vstup(cfg, backs))
    write(["rozcestnik","index.html"], page_rozcestnik(cfg))
    write(["projekty","index.html"], page_projekty(cfg, projekty))
    write(["inkubator","index.html"], page_inkubator(cfg, inkubator))
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
    if os.environ.get("USE_CNAME") == "1":
        (OUT / "CNAME").write_text("informarchitekti.cz\n")

    print(f"Hotovo: {len(projekty)} projektů, {len(inkubator)} inkubátor. Web ve složce site/.")

if __name__ == "__main__":
    main()
