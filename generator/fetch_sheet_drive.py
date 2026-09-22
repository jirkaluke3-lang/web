#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stáhne obsah z Googlu PŘED sestavením webu (cesta B):
  • data z Google Sheetu  -> data/*.csv
  • fotografie z Google Disku -> obrazky/…

Řídí se proměnnými prostředí (na GitHubu se nastaví jako "secrets"):
  GSHEET_ID       – ID Google tabulky (z její adresy)
  GDRIVE_ROOT_ID  – ID kořenové složky na Disku (web-inform)
  GDRIVE_API_KEY  – API klíč z Google Cloud (Drive API)

Když proměnné nejsou nastavené, skript nic nedělá a build použije
data/*.csv a obrazky/… tak, jak jsou v repozitáři (režim náhledu).
Používá jen standardní knihovnu Pythonu.
"""

import os, sys, json, shutil, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
IMG  = ROOT / "obrazky"

GSHEET_ID = os.environ.get("GSHEET_ID", "").strip()
ROOT_ID   = os.environ.get("GDRIVE_ROOT_ID", "").strip()
API_KEY   = os.environ.get("GDRIVE_API_KEY", "").strip()

# list v tabulce -> název souboru CSV
SHEETS = {"PROJEKTY": "projekty", "INKUBATOR": "inkubator",
          "POZADI": "pozadi", "NASTAVENI": "nastaveni"}
# podsložky na Disku, které mají vlastní podsložky projektů
SECTION_WITH_SLUGS = ["projekty", "inkubator"]
# podsložky na Disku s obrazy přímo uvnitř
SECTION_FLAT = ["pozadi", "nastaveni"]

IMG_EXT = (".jpg", ".jpeg", ".jfif", ".png", ".webp", ".avif", ".mp4", ".webm", ".gif", ".txt")


def fetch(url, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": "inform-build/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read() if binary else r.read().decode("utf-8")


# ---------------- Google Sheet ----------------
def pull_sheet():
    if not GSHEET_ID:
        print("· GSHEET_ID není nastaven — přeskakuji tabulku (použijí se data/*.csv v repu).")
        return
    DATA.mkdir(exist_ok=True)
    for sheet, fname in SHEETS.items():
        url = (f"https://docs.google.com/spreadsheets/d/{GSHEET_ID}"
               f"/gviz/tq?tqx=out:csv&sheet={urllib.parse.quote(sheet)}")
        try:
            csv_text = fetch(url)
            (DATA / f"{fname}.csv").write_text(csv_text, encoding="utf-8")
            print(f"· tabulka {sheet} -> data/{fname}.csv")
        except Exception as ex:
            print(f"! list {sheet} se nepodařilo stáhnout: {ex}")


# ---------------- Google Drive ----------------
def drive_list(folder_id):
    """Vrátí [{id,name,mimeType}] přímých potomků složky."""
    q = urllib.parse.quote(f"'{folder_id}' in parents and trashed=false")
    url = (f"https://www.googleapis.com/drive/v3/files?q={q}&key={API_KEY}"
           f"&fields=files(id,name,mimeType)&pageSize=1000&orderBy=name"
           f"&supportsAllDrives=true&includeItemsFromAllDrives=true")
    return json.loads(fetch(url)).get("files", [])


def drive_download(file_id, dest: Path):
    url = (f"https://www.googleapis.com/drive/v3/files/{file_id}"
           f"?alt=media&key={API_KEY}&supportsAllDrives=true")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(fetch(url, binary=True))


def is_folder(f): return f["mimeType"] == "application/vnd.google-apps.folder"
def is_wanted(name): return name.lower().endswith(IMG_EXT)


def pull_drive():
    if not (ROOT_ID and API_KEY):
        print("· GDRIVE_ROOT_ID / GDRIVE_API_KEY není nastaven — přeskakuji Disk (použijí se obrazky/ v repu).")
        return
    # mapa názvů sekcí -> ID
    sections = {f["name"].lower(): f["id"] for f in drive_list(ROOT_ID) if is_folder(f)}

    # vyčistit řízené složky (zdroj pravdy je Disk)
    for sec in SECTION_WITH_SLUGS + SECTION_FLAT:
        d = IMG / sec
        if d.exists(): shutil.rmtree(d)

    for sec in SECTION_WITH_SLUGS:
        if sec not in sections:
            print(f"· na Disku chybí složka '{sec}' — přeskakuji.")
            continue
        for proj in drive_list(sections[sec]):
            if not is_folder(proj): continue
            slug = proj["name"].strip()
            got, skipped, dup = 0, [], []
            for fl in drive_list(proj["id"]):
                if is_folder(fl): continue
                if not is_wanted(fl["name"]):
                    skipped.append(fl["name"]); continue
                dest = IMG / sec / slug / fl["name"]
                if dest.exists():
                    # v téhle složce na Disku je víc souborů se stejným názvem -
                    # ten druhý (a další) by přepsal ten první, proto ho radši
                    # NEstahujeme a jen na to upozorníme (žádná fotka se neztratí tiše).
                    dup.append(fl["name"]); continue
                drive_download(fl["id"], dest)
                got += 1
            msg = f"· Disk {sec}/{slug}: staženo {got} souborů"
            if skipped:
                msg += f" | PŘESKOČENO (nepodporovaný formát, převeďte na JPG): {', '.join(skipped)}"
            if dup:
                msg += f" | DUPLICITNÍ NÁZEV souboru (další soubor se stejným jménem, na Disku přejmenujte, jinak se nestáhne): {', '.join(dup)}"
            print(msg)

    for sec in SECTION_FLAT:
        if sec not in sections: continue
        got, skipped, dup = 0, [], []
        for fl in drive_list(sections[sec]):
            if is_folder(fl): continue
            if not is_wanted(fl["name"]):
                skipped.append(fl["name"]); continue
            dest = IMG / sec / fl["name"]
            if dest.exists():
                dup.append(fl["name"]); continue
            drive_download(fl["id"], dest)
            got += 1
        msg = f"· Disk {sec}/: staženo {got} souborů"
        if skipped:
            msg += f" | PŘESKOČENO (nepodporovaný formát, převeďte na JPG): {', '.join(skipped)}"
        if dup:
            msg += f" | DUPLICITNÍ NÁZEV souboru (další soubor se stejným jménem, na Disku přejmenujte, jinak se nestáhne): {', '.join(dup)}"
        print(msg)


if __name__ == "__main__":
    print("Načítám obsah z Googlu…")
    try:
        pull_sheet()
        pull_drive()
    except Exception as ex:
        print(f"! chyba při načítání z Googlu: {ex}", file=sys.stderr)
        # build i tak pokračuje z toho, co je v repu
    print("Hotovo.")
