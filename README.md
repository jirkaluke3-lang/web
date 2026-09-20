# IN—FORM—ARCHITEKTI — web

Statický web generovaný z tabulky a složek s obrazy. Běží zdarma na GitHub Pages.

## Jak přidat projekt
1. V tabulce (list **PROJEKTY**) přidej řádek — vyplň `slug`, název, lokalitu, rok,
   typ/fáze/charakter, anotaci a `seo_popis`. `publikovat` = ANO.
2. Do `obrazky/projekty/<slug>/` nahraj fotografie, pojmenované `01`, `02`, `03`…
3. (volitelně) přidej `obrazky/projekty/<slug>/popisky.txt`:
   ```
   [01]
   Hlavička obrazu (zobrazí se pod ním a slouží jako alt text)
   Delší text, který se vplete mezi obrazy v galerii.
   ```
4. Ulož / nahraj změny. Web se přegeneruje sám (záložka **Actions**).

Inkubátor funguje stejně — list **INKUBATOR** a složka `obrazky/inkubator/<slug>/`.
Vstupní pozadí: list **POZADI** + složky/soubory v `obrazky/pozadi/`.
Texty stránek O nás, Kontakt, Jobs: list **NASTAVENI**.

## Lokální náhled
```
python3 generator/build.py
# otevři site/index.html v prohlížeči
```

## Struktura
- `data/*.csv` — obsah (export z Google Sheetu)
- `obrazky/` — fotografie a videa
- `fonty/` — Ciutadella (webová licence viz níže)
- `generator/build.py` — generátor
- `site/` — vygenerovaný web (nenahrává se, staví ho Actions)

## Fonty
Řezy Ciutadella jsou zde ve formátu WOFF pro vývoj. Před ostrým spuštěním
na veřejné doméně ověř u Emtype Foundry webovou licenci.
