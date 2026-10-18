"""Nesine Spor Toto sonuçlarını okuyup veri/sonuclar.json dosyasına yazar.

GitHub Actions tarafından 15 dakikada bir çalıştırılır. Sadece herkese açık sonuç sayfasını okur;
hiçbir kişisel veri, kupon ya da şifre içermez. Değişiklik yoksa dosyaya dokunmaz.
"""
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

DOSYA = Path(__file__).resolve().parent.parent / "veri" / "sonuclar.json"
URL = "https://www.nesine.com/sportoto"
ILK_SEFER = 26     # dosya boşken geriye doğru kaç hafta çekilsin
HER_SEFER = 3      # her çalışmada en yeni kaç hafta kontrol edilsin (bitmemiş olanlar)
TR = timezone(timedelta(hours=3))

JS_SONUC = """() => {
  const sel = document.querySelector('#filter-week-select');
  const secenek = sel ? [...sel.options].map(o => ({deger: o.value, metin: o.textContent.trim()})) : [];
  const secili = sel ? sel.options[sel.selectedIndex].textContent.trim() : '';
  const hucre = (tr, k) => { const e = tr.querySelector(`td[data-test-id="programResult-${k}"]`); return e ? e.innerText.trim() : ''; };
  const satirlar = [...document.querySelectorAll('tr')].filter(tr => tr.querySelector('td[data-test-id="programResult-name"]'))
    .map(tr => ({no: parseInt(hucre(tr,'number')), tarih: hucre(tr,'date'), ad: hucre(tr,'name'),
                 durum: hucre(tr,'status'), sonuc: hucre(tr,'result')}));
  const ikramiye = [...document.querySelectorAll('tr')].map(tr => [...tr.querySelectorAll('td')].map(x => x.innerText.trim()))
    .filter(c => c.length >= 3 && /^\\d{2}\\s*Bilen/i.test(c[0]))
    .map(c => ({bilen: parseInt(c[0]), adet: parseInt(c[1].replace(/\\D/g,'')) || 0,
                kazanc: parseFloat(c[2].replace(/[^\\d,]/g,'').replace(',','.')) || 0}));
  return {secenek, secili, satirlar, ikramiye};
}"""


def tamam_mi(h, sira):
    s = [r.get("sonuc") for r in h.get("maclar", [])]
    hepsi = len(s) == 15 and all(x in ("1", "X", "2") for x in s)
    return hepsi and (bool(h.get("ikramiye")) or sira >= HER_SEFER)


def kaydet_hafta(v):
    maclar = []
    for r in v["satirlar"][:15]:
        sonuc = (r.get("sonuc") or "").strip().upper().replace("0", "X")
        maclar.append({"no": r.get("no"), "tarih": r.get("tarih", ""), "ad": r.get("ad", ""),
                       "durum": r.get("durum", ""), "sonuc": sonuc if sonuc in ("1", "X", "2") else None})
    return {"maclar": maclar, "ikramiye": v.get("ikramiye") or []}


def imza(v):
    return "|".join(r["ad"] + r["tarih"] for r in v["satirlar"][:3])


def secime_gec(s, deger, metin, onceki):
    s.select_option("#filter-week-select", deger)
    bas = time.time()
    v = None
    while time.time() - bas < 15:
        time.sleep(0.7)
        v = s.evaluate(JS_SONUC)
        if v["secili"] == metin and v["satirlar"] and imza(v) != onceki:
            time.sleep(0.8)
            return s.evaluate(JS_SONUC)
    return v


def main():
    eski = json.loads(DOSYA.read_text(encoding="utf-8")) if DOSYA.exists() else {"haftalar": {}}
    haftalar = dict(eski.get("haftalar") or {})
    yeni = {}
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        s = b.new_page(locale="tr-TR", viewport={"width": 1300, "height": 900},
                       user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                  "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
        s.goto(URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(5)
        s.get_by_role("button", name="Sonuçlar", exact=True).first.click(timeout=30000)
        s.wait_for_selector("#filter-week-select", timeout=30000)
        time.sleep(3)
        v = s.evaluate(JS_SONUC)
        secenek = v["secenek"]
        sinir = HER_SEFER if haftalar else ILK_SEFER
        son_imza = imza(v)
        for sira, o in enumerate(secenek[:ILK_SEFER]):
            mevcut = haftalar.get(o["metin"])
            if mevcut and (sira >= sinir or tamam_mi(mevcut, sira)):
                continue
            try:
                v2 = v if o["metin"] == v["secili"] else secime_gec(s, o["deger"], o["metin"], son_imza)
            except Exception as e:
                print("uyarı:", o["metin"], e, file=sys.stderr)
                continue
            if v2 and v2["secili"] == o["metin"] and len(v2["satirlar"]) >= 15:
                yeni[o["metin"]] = kaydet_hafta(v2)
                son_imza = imza(v2)
        b.close()
    degisti = False
    simdi = datetime.now(TR).strftime("%Y-%m-%d %H:%M")
    for ar, h in yeni.items():
        onceki = haftalar.get(ar) or {}
        if {k: onceki.get(k) for k in ("maclar", "ikramiye")} != h:
            haftalar[ar] = {**h, "guncel": simdi}
            degisti = True
    sira = [o["metin"] for o in secenek]
    haftalar = dict(sorted(haftalar.items(), key=lambda kv: sira.index(kv[0]) if kv[0] in sira else 999)[:60])
    if degisti or not DOSYA.exists():
        DOSYA.parent.mkdir(exist_ok=True)
        DOSYA.write_text(json.dumps({"guncel": simdi, "kaynak": "nesine.com/sportoto", "haftalar": haftalar},
                                    ensure_ascii=False, indent=0), encoding="utf-8")
    print(("güncellendi: " + ", ".join(yeni)) if degisti else "değişiklik yok", "| okunan:", len(yeni))


if __name__ == "__main__":
    main()
