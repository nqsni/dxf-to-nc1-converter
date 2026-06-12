# NC1 Converter — Web App

Tool internal untuk konversi file DXF pelat baja → NC1 (DSTV) via browser.

---

## Struktur Folder

```
nc1app/
├── app.py          ← Flask server (jalankan ini)
├── converter.py    ← Logic konversi DXF → NC1
├── templates/
│   └── index.html  ← Tampilan web
├── uploads/        ← File DXF sementara (otomatis terhapus)
└── outputs/        ← File NC1 sementara (otomatis terhapus setelah download)
```

---

## Instalasi (sekali saja)

**1. Install Python** (jika belum):  
→ https://python.org/downloads (pilih versi 3.10 ke atas)

**2. Install library:**
```bash
pip install flask ezdxf
```

---

## Cara Menjalankan

**Buka terminal / Command Prompt di folder `nc1app/`, lalu:**

```bash
python app.py
```

Output:
```
==================================================
  NC1 Converter Web App
  Akses lokal  : http://localhost:5000
  Akses jaringan: http://<IP-komputer>:5000
==================================================
```

**Buka browser → http://localhost:5000**

---

## Akses dari Komputer Lain (Intranet Kantor)

Agar user lain di jaringan yang sama bisa akses:

1. Cari IP komputer server:
   - Windows: buka CMD → ketik `ipconfig` → lihat "IPv4 Address" (contoh: `192.168.1.50`)
   - Mac/Linux: `ifconfig` atau `ip addr`

2. Pastikan **firewall** mengizinkan port 5000:
   - Windows: Windows Defender Firewall → Allow an app → tambahkan Python pada port 5000

3. User lain buka browser → ketik: `http://192.168.1.50:5000`

---

## Cara Pakai

1. Drag & drop file `.dxf` ke area upload (atau klik untuk pilih)
2. Isi **Ketebalan** pelat (mm)
3. Pilih **Grade Baja** dari dropdown
4. Klik **Convert ke NC1**
5. Preview NC1 muncul → klik **Download NC1**

### Field opsional:
- **Mark / Kode Pelat** — jika kosong, otomatis dari nama file
- **Jumlah (pcs)** — default: 1
- **Kode Proyek** — baris identifikasi proyek di header NC1

---

## Menjalankan Otomatis saat Windows Menyala (Opsional)

Buat file `start_nc1.bat`:
```bat
@echo off
cd /d "C:\path\ke\nc1app"
python app.py
pause
```
Lalu taruh shortcut-nya di:  
`C:\Users\[nama]\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup`

---

## Catatan

- File DXF yang diupload **langsung dihapus** setelah diproses
- File NC1 **dihapus otomatis** setelah didownload
- Tidak ada data yang disimpan permanen di server
