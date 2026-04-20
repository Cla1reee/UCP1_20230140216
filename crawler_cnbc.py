import os
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import datetime
import time
import pymongo 

# Memuat konfigurasi dari file .env
load_dotenv()

def crawl_cnbc_esg_antibot():
    waktu_sekarang = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{waktu_sekarang}] Memulai Chrome Anti-Bot...")
    
    # Konfigurasi MongoDB dari Environment Variables
    MONGO_URI = os.getenv("MONGODB_URI")
    DB_NAME = os.getenv("DB_NAME")
    COLLECTION_NAME = os.getenv("COLLECTION_NAME")

    chrome_options = Options()
    # Aktifkan kembali headless jika sudah yakin jalan di Task Scheduler
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    scraped_data = []
    driver = None
    
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
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
            if 'cnbcindonesia.com' in href and any(k in href for k in ['/news/', '/market/', '/tech/', '/entrepreneur/', '/syariah/', '/lifestyle/']):
                if href not in url_berita_list: 
                    url_berita_list.append(href)
        
        if not url_berita_list:
            print("❌ Peringatan: Tidak ada URL artikel yang ditemukan.")
            return
            
        print(f"✅ Ditemukan {len(url_berita_list)} URL artikel. Memulai ekstraksi...")

        # Ambil semua berita (hapus [:5] untuk produksi)
        for i, url_berita in enumerate(url_berita_list, 1): 
            try:
                print(f"   [{i}/{len(url_berita_list)}] Merender: {url_berita}")
                driver.get(url_berita)
                driver.execute_script("window.scrollTo(0, 500);")
                time.sleep(4) 
                
                art_soup = BeautifulSoup(driver.page_source, "html.parser")
                judul_tag = art_soup.find("h1")
                judul = judul_tag.text.strip() if judul_tag else "Judul tidak ditemukan"
                
                if judul == "Judul tidak ditemukan":
                    continue
                
                date_meta = art_soup.find("meta", attrs={"name": "dtk:publishdate"}) or art_soup.find("meta", attrs={"name": "publishdate"})
                tanggal = date_meta["content"] if date_meta else "Tanggal tidak ditemukan"
                
                author_meta = art_soup.find("meta", attrs={"name": "dtk:author"}) or art_soup.find("meta", attrs={"name": "author"})
                author = author_meta["content"] if author_meta else "Author tidak ditemukan"
                
                tags_meta = art_soup.find("meta", attrs={"name": "dtk:keywords"}) or art_soup.find("meta", attrs={"name": "keywords"})
                tag_kategori = [tag.strip() for tag in tags_meta["content"].split(',')] if tags_meta else []
                
                body = art_soup.find("div", class_="detail_text") or art_soup.find("article")
                isi_berita = "\n".join([p.text.strip() for p in body.find_all("p")]) if body else "Isi tidak ditemukan"
                
                thumb_meta = art_soup.find("meta", property="og:image")
                thumbnail = thumb_meta["content"] if thumb_meta else "Thumbnail tidak ditemukan"
                
                scraped_data.append({
                    "url": url_berita,
                    "judul": judul,
                    "tanggal_publish": tanggal,
                    "author": author,
                    "tag_kategori": tag_kategori,
                    "isi_berita": isi_berita,
                    "thumbnail": thumbnail
                })
                    
            except Exception as e:
                print(f"❌ Gagal membaca detail: {e}")

        # Integrasi MongoDB Cloud menggunakan variabel dari .env
        if scraped_data and MONGO_URI:
            print("\n⏳ Mengunggah data ke MongoDB Atlas...")
            try:
                client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
                db = client[DB_NAME]
                collection = db[COLLECTION_NAME]
                
                collection.delete_many({}) 
                collection.insert_many(scraped_data)
                print(f"☁️ SUKSES: {len(scraped_data)} data berhasil diunggah!")
            except Exception as mongo_error:
                print(f"❌ GAGAL MONGODB: {mongo_error}")
                
    except Exception as e:
        print(f"❌ Kesalahan Sistem Utama: {e}")
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    crawl_cnbc_esg_antibot()