# Toto Cep

Spor Toto kolonlarını telefondan takip etmek için kişisel site.

- `index.html` — telefon sitesi (GitHub Pages ile yayınlanır).
- `robot/sonuc_robot.py` + `.github/workflows/sonuclar.yml` — Nesine'nin herkese açık Spor Toto sonuç
  sayfasını 15 dakikada bir okuyup `veri/sonuclar.json` dosyasına yazar.
- `veri/e/*.json` — bilgisayardaki Toto Masası'nın "Telefona yayınla" düğmesiyle gönderdiği **şifreli** kolon
  dosyaları. Şifreler sadece kişiye özel bağlantılarda bulunur; bu depoda yoktur.
