import os
from fpdf import FPDF

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'Nakit Akim - Yeni Sunucu Mimari Gecis Plani', ln=True, align='C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Sayfa {self.page_no()}', 0, 0, 'C')

def create_pdf():
    pdf = PDF()
    
    pdf.add_font('Arial', '', '/System/Library/Fonts/Supplemental/Arial.ttf', uni=True)
    pdf.add_font('Arial', 'B', '/System/Library/Fonts/Supplemental/Arial Bold.ttf', uni=True)
    pdf.add_font('Arial', 'I', '/System/Library/Fonts/Supplemental/Arial Italic.ttf', uni=True)
    
    pdf.add_page()
    pdf.set_font('Arial', '', 10)
    
    turkish_text = """Harika bir mimari plan! Kendi sunucunuzu (Windows Server 2012) kullanma fikri, özellikle fatura PDF/Görselleri gibi çok yer kaplayacak dosyalar söz konusu olduğunda disk maliyetinizi neredeyse sıfıra indirecektir.

Bu yapıya geçiş için düşündüğünüz plan teknik olarak çok doğru. Süreci pürüzsüz atlatmak ve ileride sorun yaşamamak için şu detaylara dikkat etmenizi tavsiye ederim:

1. Dosya (Blob) Yönetimi
Sunucunuzda bolca disk alanı olsa bile, faturaları PostgreSQL veritabanının içine (bytea) kaydetmek yerine, uygulamanızın bulunduğu bir klasöre (Örneğin: C:\WebAdmin\Faturalar) kaydetmenizi ve veritabanına sadece bu dosyanın yolunu veya linkini kaydetmenizi yine de tavsiye ederim.
* Neden? Veritabanı çok hızlı çalışmaya devam eder, yedekleme (backup) saniyeler sürer ve web arayüzünüz üzerinden http://sunucu-ip/faturalar/fatura.pdf şeklinde dünyanın her yerinden anında erişebilirsiniz.

2. Veritabanı (Neon) Göçü (Migration)
Mevcut Neon veritabanınızı kendi sunucunuza aktarmak için size bir komut dosyası (script) hazırlayabilirim. PostgreSQL'in pg_dump aracını kullanarak Neon'daki tüm verilerinizi (tablolar, müşteriler, geçmiş işlemler) tam yedeğini alıp kendi Server 2012 makinenizdeki PostgreSQL'e eksiksiz aktarabiliriz.

3. Güvenlik ve Uzaktan Erişim (Çok Önemli)
Server 2012 makinenize "tüm dünyadan" bağlanacağınızı belirttiniz. 
* Kendi masaüstü nakit akım uygulamanız, uzaktaki sunucunuzdaki veritabanına doğrudan bağlanacaksa PostgreSQL portunu (5432) dışarıya (internete) açmanız gerekecektir.
* Tavsiye: Veritabanını doğrudan dışarıya açmak yerine, cemergun34/webadmin-nakitakim projenizin bir API gibi davranıp verileri masaüstü uygulamanıza iletmesi veya PostgreSQL'i çok güçlü bir şifre ve sadece belirli IP'lere (veya VPN'e) izin verecek şekilde yapılandırmanız güvenliğiniz için hayati önem taşır.

--------------------------------------------------------------------------------
WINDOWS SERVER 2012 ÜZERİNDE GÜVENLİ POSTGRESQL VE WEB-API KURULUM REHBERİ
--------------------------------------------------------------------------------
Windows Server 2012'nin resmi güvenlik desteği sona erdiği için sunucuyu dış dünyaya (internete) doğrudan açmak ciddi riskler barındırır. Bu nedenle güvenliği maksimum seviyede tutmalıyız:

ADIM 1: Güvenli PostgreSQL Kurulumu
1. PostgreSQL 14 veya 15 sürümünü indirin (Daha yeni sürümler Server 2012'de sorun çıkarabilir).
2. Kurulum sırasında varsayılan 'postgres' kullanıcısı için çok karmaşık, tahmin edilemez bir şifre belirleyin (Örn: 'Nkt_2026!xYz#').
3. Veritabanının sadece yerel sunucuda (localhost) veya VPN IP'lerinde çalışmasını sağlayın. Dışarıya açık port kullanmayın.

ADIM 2: Dışarıdan Erişimi Kapatma (pg_hba.conf ayarları)
1. "C:\\Program Files\\PostgreSQL\\14\\data\\pg_hba.conf" dosyasını açın.
2. Tüm dış IP'lere izin veren (0.0.0.0/0) satırları SİLİN.
3. Sadece uygulamanızın (WebAdmin) çalıştığı IP'ye (127.0.0.1) izin verin:
   host    all             all             127.0.0.1/32            scram-sha-256

ADIM 3: WebAdmin (API) Üzerinden Güvenli İletişim (POST İşlemleri)
Veritabanı portunu (5432) internete açmak yerine, masaüstü uygulamanız ile sunucunuz arasındaki iletişimi WebAdmin projeniz (cemergun34/webadmin-nakitakim) üzerinden HTTP POST istekleriyle sağlayın:
1. WebAdmin Projenizi IIS veya Nginx/Apache arkasında çalıştırın.
2. SSL (HTTPS) Sertifikası Kurun: İletişimin şifrelenmesi şarttır. Let's Encrypt veya Cloudflare kullanarak ücretsiz SSL sertifikası kurun.
3. API Uç Noktaları Oluşturun: Masaüstü uygulamanız, doğrudan veritabanına SQL atmak yerine, WebAdmin'deki bir adrese POST isteği göndersin (Örn: https://sunucunuz.com/api/fatura_kaydet).
4. Yetkilendirme (Token): Bu POST isteklerinin sadece sizden geldiğini doğrulamak için bir API Key (Anahtar) veya Bearer Token mekanizması kullanın. Her POST isteğinin başlığında (Header) bu gizli anahtar bulunsun.

--------------------------------------------------------------------------------
ÖZET VE KRİTİK DETAYLAR
--------------------------------------------------------------------------------
- PostgreSQL 14 veya 15 sürümünün tercih edilmesi.
- Dışarıdan doğrudan erişimin (pg_hba.conf üzerinden) tamamen engellenmesi.
- İletişimin web sunucusu (IIS/Nginx) arkasında SSL/HTTPS sertifikası ile şifrelenmesi.
- Doğrudan veritabanı portunu açmak yerine işlemlerin WebAdmin üzerinden güvenli HTTP POST istekleri (API Token/Key korumalı) ile yapılması.
--------------------------------------------------------------------------------

Nasıl ilerleyelim?
Eğer uzak sunucunuzdaki PostgreSQL kurulumu hazırsa;
1. Neon'daki mevcut verilerinizin yedeğini (dump) almanıza,
2. Bu yedeği yeni sunucunuza yüklemenize,
3. WebAdmin projenizde API uç noktalarını hazırlamaya...

Hangi adımdan başlamamı istersiniz? İstediğiniz zaman bu geçiş işlemlerini beraber yapabiliriz.
"""
    
    pdf.multi_cell(0, 6, turkish_text)
    
    output_path = os.path.join(os.path.expanduser('~'), 'Desktop', 'Mimari_Gecis_Plani.pdf')
    pdf.output(output_path)
    print(f"PDF olusturuldu: {output_path}")

if __name__ == '__main__':
    create_pdf()
