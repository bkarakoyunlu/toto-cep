"""GitHub üzerinde Nesine Spor Toto sayfasının okunup okunamadığını dener."""
import json, time, urllib.request, pathlib
from playwright.sync_api import sync_playwright
JS_PROGRAM = """() => {
  const rows = [...document.querySelectorAll('tr')].filter(tr => tr.querySelector('td[data-test-id="name"]'));
  const yuzde = (tr, k) => { const e = tr.querySelector(`td[data-test-id="percentage${k}"]`);
      return e ? parseFloat(e.innerText.replace('%','').replace(',','.')) : null; };
  const out = rows.slice(0, 15).map(tr => {
    const td = [...tr.querySelectorAll('td')].map(x => x.innerText.trim());
    return { no: parseInt(td[0]), tarih: td[1], ad: tr.querySelector('td[data-test-id="name"]').innerText.trim(),
             tercih: [yuzde(tr,1), yuzde(tr,0), yuzde(tr,2)] };
  });
  const th = [...document.querySelectorAll('th')].find(x => /Programı/.test(x.innerText));
  const st = [...document.querySelectorAll('div,span,p')].filter(x => /son tarih/i.test(x.innerText) && x.innerText.length < 80)
      .sort((a,b) => a.innerText.length - b.innerText.length)[0];
  return { baslik: th ? th.innerText.trim() : '', son_tarih: st ? st.innerText.trim() : '', maclar: out };
}"""
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
out = {"zaman": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())}
try:
    out["konum"] = json.loads(urllib.request.urlopen("https://ipinfo.io/json", timeout=10).read())
    out["konum"] = {k: out["konum"].get(k) for k in ("country", "region", "org")}
except Exception as e:
    out["konum"] = str(e)
d = pathlib.Path("cikti"); d.mkdir(exist_ok=True)
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    s = b.new_page(locale="tr-TR", viewport={"width": 1300, "height": 900},
                   user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36")
    try:
        r = s.goto("https://www.nesine.com/sportoto", wait_until="domcontentloaded", timeout=60000)
        out["http"] = r.status if r else None
        time.sleep(8)
        out["baslik"] = s.title()
        out["url"] = s.url
        s.screenshot(path="cikti/1_ana.png")
        try:
            out["program"] = s.evaluate(JS_PROGRAM)
        except Exception as e:
            out["program_hata"] = str(e)[:300]
        try:
            s.get_by_role("button", name="Sonuçlar", exact=True).first.click(timeout=20000)
            s.wait_for_selector("#filter-week-select", timeout=30000)
            time.sleep(3)
            out["sonuc"] = s.evaluate(JS_SONUC)
        except Exception as e:
            out["sonuc_hata"] = str(e)[:300]
        s.screenshot(path="cikti/2_sonuc.png")
        out["metin_basi"] = s.inner_text("body")[:1500]
    except Exception as e:
        out["hata"] = str(e)[:500]
    b.close()
json.dump(out, open("cikti/sonuc_testi.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps({k: out.get(k) for k in ("konum", "http", "baslik", "url", "hata", "sonuc_hata")}, ensure_ascii=False))
print("program maç:", len((out.get("program") or {}).get("maclar", [])), "sonuç satırı:", len((out.get("sonuc") or {}).get("satirlar", [])))
