import json,sys,traceback,collections
sys.path.insert(0,"tani")
import oran_robot as o
out={}
try:
    v=o.bulten_indir()
    ea=(v.get("sg") or {}).get("EA") or []
    out["toplam"]=len(ea); out["anahtarlar"]=list(v.keys())[:10]; out["sg_anahtar"]=list((v.get("sg") or {}).keys())[:10]
    out["tip"]=dict(collections.Counter((e.get("TYPE"),e.get("GT"),bool(e.get("LE"))) for e in ea).most_common(8)).__repr__()
    out["ornek"]=[{k:e.get(k) for k in ("HN","AN","D","T","TYPE","GT","LE","C")} for e in ea if any(w in (str(e.get("HN"))+str(e.get("AN"))).lower() for w in ("alanya","kasımpaşa","kasimpasa","beşiktaş","besiktas","galatasaray","dortmund","chelsea"))][:12]
    maclar=json.load(open("tani/maclar.json"))
    out["esles"]=o.eslestir(v,maclar,"23.10.2026 - 27.10.2026")
    if out["ornek"]:
        e=[x for x in ea if "alanya" in str(x.get("HN")).lower()][:1]
        if e: out["ornek_ma"]=json.dumps(e[0].get("MA") or [],ensure_ascii=False)[:1500]
except Exception as ex:
    out["hata"]=traceback.format_exc()[-1500:]
json.dump(out,open("tani/sonuc.json","w"),ensure_ascii=False,indent=1,default=str)
print(json.dumps({k:out.get(k) for k in ("toplam","tip","hata")},ensure_ascii=False,default=str))
