from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import datetime
import time
import pymongo 

def crawl_cnbc_esg_antibot():
    waktu_sekarang = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{waktu_sekarang}] Memulai Chrome Anti-Bot...")
    
    # 1. Konfigurasi Selenium (ANTI-BOT & VISIBLE MODE)
    chrome_options = Options()
    # SAYA MATIKAN HEADLESS AGAR ANDA BISA MELIHAT LAYAR CHROME-NYA LANGSUNG
    # chrome_options.add_argument("--headless") 
    
    # Teknik menyamarkan Selenium agar terlihat seperti manusia asli
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    scraped_data = []
    driver = None
    
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        
        # Mengecoh deteksi navigator webdriver milik javascript
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
        })
        
        search_url = "https://www.cnbcindonesia.com/search?query=environmental+sustainability"
        print("⏳ Mengakses halaman pencarian...")
        driver.get(search_url)
        time.sleep(5) 
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        all_links = soup.find_all("a", href=True)
        url_berita_list = []
        
        for a in all_links:
            href = a['href']
            if 'cnbcindonesia.com' in href and any(kategori in href for kategori in ['/news/', '/market/', '/tech/', '/entrepreneur/', '/syariah/', '/lifestyle/']):
                if href not in url_berita_list: 
                    url_berita_list.append(href)
        
        if not url_berita_list:
            print("❌ Peringatan: Tidak ada URL artikel yang ditemukan.")
            return
            
        print(f"✅ Ditemukan {len(url_berita_list)} URL artikel. Memulai ekstraksi...")

        # 2. Loop Ekstraksi Detail (Terlihat di Layar)
        for i, url_berita in enumerate(url_berita_list[:5], 1): # KITA BATASI 5 DULU UNTUK TESTING
            try:
                print(f"   [{i}/5] Merender: {url_berita}")
                driver.get(url_berita)
                
                # Scroll sedikit ke bawah untuk memancing lazy-loading gambar/teks
                driver.execute_script("window.scrollTo(0, 500);")
                time.sleep(4) 
                
                art_soup = BeautifulSoup(driver.page_source, "html.parser")
                
                # 1. URL
                url_final = url_berita
                
                # 2. Judul (Pencarian Agresif)
                judul_tag = art_soup.find("h1")
                judul = judul_tag.text.strip() if judul_tag else "Judul tidak ditemukan"
                
                # JIKA JUDUL MASIH KOSONG, BERARTI KENA CLOUDFLARE CAPTCHA
                if judul == "Judul tidak ditemukan":
                    print("       ⚠️ TERDETEKSI BLOKIR CLOUDFLARE / CAPTCHA! Halaman gagal dimuat.")
                    continue
                
                # 3. Tanggal Publish (Memanfaatkan tag khusus Detik Network)
                date_meta = art_soup.find("meta", attrs={"name": "dtk:publishdate"}) or art_soup.find("meta", attrs={"name": "publishdate"}) or art_soup.find("div", class_="date")
                tanggal = date_meta["content"] if date_meta and date_meta.name == "meta" else (date_meta.text.strip() if date_meta else "Tanggal tidak ditemukan")
                
                # 4. Author 
                author_meta = art_soup.find("meta", attrs={"name": "dtk:author"}) or art_soup.find("meta", attrs={"name": "author"})
                author = author_meta["content"] if author_meta else "Author tidak ditemukan"
                
                # 5. Tag Kategori
                tags_meta = art_soup.find("meta", attrs={"name": "dtk:keywords"}) or art_soup.find("meta", attrs={"name": "keywords"})
                tag_kategori = [tag.strip() for tag in tags_meta["content"].split(',')] if tags_meta else []
                
                # 6. Isi Berita (Mencari semua Paragraf <p> di dalam kotak artikel)
                body = art_soup.find("div", class_="detail_text") or art_soup.find("div", class_="detail-text") or art_soup.find("article")
                if body:
                    paragraphs = body.find_all("p")
                    isi_berita = "\n".join([p.text.strip() for p in paragraphs if p.text.strip() != ""])
                else:
                    isi_berita = "Isi berita tidak ditemukan."
                    
                # 7. Thumbnail
                thumb_meta = art_soup.find("meta", property="og:image") or art_soup.find("meta", attrs={"name": "dtk:thumbnailUrl"})
                thumbnail = thumb_meta["content"] if thumb_meta else "Thumbnail tidak ditemukan"
                
                scraped_data.append({
                    "url": url_final,
                    "judul": judul,
                    "tanggal_publish": tanggal,
                    "author": author,
                    "tag_kategori": tag_kategori,
                    "isi_berita": isi_berita,
                    "thumbnail": thumbnail
                })
                print(f"       ✔️ Ekstrak Sukses: {judul[:40]}...")
                    
            except Exception as e:
                print(f"❌ Gagal membaca: {url_berita} | Error: {e}")

        print("-" * 60)
        
        # 3. Integrasi MongoDB Cloud
        if scraped_data:
            print("\n⏳ Mengunggah data ke MongoDB Atlas...")
            # GANTI URI DI BAWAH INI DENGAN KREDENSIAL ASLI ANDA
            uri = "mongodb+srv://hapis_db_user:HAPIS2908@mongodb.aaorcaw.mongodb.net/?retryWrites=true&w=majority"
            
            try:
                client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=5000)
                client.admin.command('ping') 
                
                db = client["UCP_CloudDatabase"]
                collection = db["Berita_CNBC"]
                
                # Hapus data lama yang rusak
                collection.delete_many({}) 
                collection.insert_many(scraped_data)
                print(f"☁️ SUKSES: {len(scraped_data)} data percobaan berhasil diunggah!")
            except Exception as mongo_error:
                print(f"❌ GAGAL MONGODB: {mongo_error}")
                
    except Exception as e:
        print(f"❌ Kesalahan Sistem Utama: {e}")
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    crawl_cnbc_esg_antibot()