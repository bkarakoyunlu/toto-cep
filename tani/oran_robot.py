"""Oran robotu: bültendeki 15 maçın iddaa oranlarını Nesine'nin herkese açık bülten verisinden çeker.

Token harcamaz, yapay zeka kullanmaz; sadece bu bilgisayardan Nesine'ye tek bir istek atar.
Dünyadaki diğer maçlar okunur ama KAYDEDİLMEZ; sadece 15 bülten maçıyla eşleşenler döner.
"""
import gzip
import json
import os
import re
import unicodedata
import urllib.request
from datetime import datetime, timedelta

NESINE_BULTEN = os.environ.get("TOTO_BULTEN_URL") or "https://cdnbulten.nesine.com/api/bulten/getprebultenfull"
_TR = str.maketrans("çğıöşüÇĞİÖŞÜâîû", "cgiosuCGIOSUaiu")
_GEREKSIZ = {"a", "s", "as", "fk", "fc", "sk", "jk", "kulubu", "spor", "kulub", "cf", "ac", "sc", "afc",
             "1907", "1903", "1905", "1906", "sportif", "faaliyetler", "the", "de", "club"}
_GENC = re.compile(r"\b(u\d{2}|k|kadin|kadinlar|women|w|ii|b|rezerv|reserves?)\b")


def sade(ad):
    s = unicodedata.normalize("NFKC", str(ad or "")).translate(_TR).lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return s


# Türkçe yazımlar -> uluslararası yazım (Sofascore vb. İngilizce ad kullanır)
_ESDEGER = {"munih": "munchen", "marsilya": "marseille", "lizbon": "lisbon", "kopenhag": "copenhagen", "prag": "prague",
            "koln": "koln", "monchengladbach": "monchengladbach", "bruj": "brugge", "atletico": "atletico",
            "psg": "paris", "saint": "saint", "betis": "betis", "bilbao": "bilbao", "napoli": "napoli",
            "inter": "inter", "milano": "milan", "torino": "torino", "londra": "london", "amedspor": "amed",
            "istanbul": "", "jk": "", "basaksehir": "basaksehir", "cykr": "caykur", "rize": "rizespor"}


def kelimeler(ad):
    out = []
    for w in sade(ad).split():
        w = _ESDEGER.get(w, w)
        if w and w not in _GEREKSIZ and len(w) > 1:
            out.append(w)
    return out


def benzerlik(a, b):
    """0..1 arası; kelime ya da ilk 4 harf eşleşmesi."""
    ka, kb = kelimeler(a), kelimeler(b)
    if not ka or not kb:
        return 0.0
    if _GENC.search(sade(b)) and not _GENC.search(sade(a)):
        return 0.0  # U19, kadın, B takımı vb. karışmasın
    def es(x, y):
        return x == y or (len(x) >= 4 and len(y) >= 4 and (x[:4] == y[:4] or x in y or y in x))
    ortak = sum(1 for x in ka if any(es(x, y) for y in kb))
    return ortak / max(len(ka), 1) * 0.7 + ortak / max(len(kb), 1) * 0.3


def bulten_indir(zaman_asimi=25):
    r = urllib.request.Request(NESINE_BULTEN, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept": "application/json", "Accept-Encoding": "gzip", "Referer": "https://www.nesine.com/"})
    with urllib.request.urlopen(r, timeout=zaman_asimi) as y:
        ham = y.read(60_000_000)
        if y.headers.get("Content-Encoding") == "gzip":
            ham = gzip.decompress(ham)
    return json.loads(ham.decode("utf-8"))


def _oranlar(ev):
    o = {}
    for m in ev.get("MA") or []:
        oca = {c.get("N"): c.get("O") for c in m.get("OCA") or []}
        if m.get("MTID") == 1 and len(oca) >= 3:
            o.update({"1": oca.get(1), "X": oca.get(2), "2": oca.get(3)})
    return {k: float(v) for k, v in o.items() if v}


def _aralik(program_araligi):
    t = re.findall(r"(\d{2})\.(\d{2})\.(\d{4})", program_araligi or "")
    if len(t) < 2:
        return None
    a, b = [datetime(int(y), int(m), int(d)) for d, m, y in t[:2]]
    return a - timedelta(days=2), b + timedelta(days=2)


def eslestir(veri, maclar, program_araligi=""):
    """15 maçın her biri için en iyi eşleşen iddaa maçını ve oranlarını döndürür."""
    sinir = _aralik(program_araligi)
    adaylar = []
    for ev in (veri.get("sg") or {}).get("EA") or []:
        if ev.get("TYPE") != 1 or ev.get("GT") != 1 or ev.get("LE"):
            continue
        if sinir:
            try:
                g = datetime.strptime(ev.get("D", ""), "%d.%m.%Y")
                if not (sinir[0] <= g <= sinir[1]):
                    continue
            except ValueError:
                pass
        adaylar.append(ev)
    out = []
    for i, m in enumerate(maclar[:15]):
        ev_ad, dep_ad = m.get("ev") or "", m.get("dep") or ""
        if not ev_ad and m.get("nesine_ad") and "-" in m["nesine_ad"]:
            ev_ad, dep_ad = m["nesine_ad"].split("-", 1)
        en, puan = None, 0.0
        for a in adaylar:
            p = min(benzerlik(ev_ad, a.get("HN")), benzerlik(dep_ad, a.get("AN")))
            if p > puan:
                en, puan = a, p
        if en is None or puan < 0.5:
            out.append({"i": i, "bulundu": False})
            continue
        o = _oranlar(en)
        out.append({"i": i, "bulundu": bool(o.get("1")), "iddaa_ad": f'{en.get("HN")} - {en.get("AN")}',
                    "tarih": f'{en.get("D", "")} {en.get("T", "")}'.strip(), "kod": en.get("C"),
                    "guven": round(puan, 2), "oran": o})
    return out


def cek(maclar, program_araligi=""):
    veri = bulten_indir()
    return {"zaman": datetime.now().isoformat(timespec="seconds"), "kaynak": "Nesine (iddaa bülteni)",
            "maclar": eslestir(veri, maclar, program_araligi)}
