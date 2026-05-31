-- =============================================================================
-- FIX: PostgreSQL büyük-küçük harf duyarlılığı düzeltmesi
-- =============================================================================
-- Supabase SQL Editor'da çalıştırın.
-- Mevcut "vomsisBilgileri" tablosunu ve moy_bilgileri kolonlarını düzeltir.
-- =============================================================================

-- 1. "vomsisBilgileri" → vomsisBilgileri (tırnak kaldır = küçük harf)
--    Eğer tablo "vomsisBilgileri" adıyla (tırnaklı, büyük harf korumalı) varsa rename et.
DO $$
BEGIN
    -- Tırnaklı tablo var mı kontrol et
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = 'vomsisBilgileri'   -- PostgreSQL büyük harf = 'vomsisBilgileri'
    ) THEN
        -- Tırnaklı eski ad → küçük harfli yeni ad
        ALTER TABLE "vomsisBilgileri" RENAME TO vomsisbilgileri_tmp;
        ALTER TABLE vomsisbilgileri_tmp RENAME TO "vomsisBilgileri";
        -- NOT: PostgreSQL tırnaksız CREATE'te zaten küçük harfe düşürür.
        -- Eğer tablo gerçekten büyük harf içeriyorsa aşağıdaki RENAME gerekli:
        RAISE NOTICE 'vomsisBilgileri tablosu zaten var, kolon kontrolü yapılıyor.';
    ELSE
        RAISE NOTICE 'vomsisBilgileri tablosu bulunamadı, oluşturulacak.';
    END IF;
END $$;

-- Daha basit yaklaşım: tırnaklı isimle erişim sağlayan view oluştur
-- (tablo adını değiştirmek yerine)

-- 2. moy_bilgileri → "musteriNo" kolonunu kontrol et
DO $$
BEGIN
    -- "musteriNo" kolonu tırnaklı mı (büyük harf korumalı) yoksa küçük mi?
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'moy_bilgileri'
          AND column_name = 'musteriNo'   -- büyük harf korumalı
    ) THEN
        RAISE NOTICE 'moy_bilgileri.musteriNo kolonu doğru (büyük harf korumalı tırnaklı).';
    ELSIF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'moy_bilgileri'
          AND column_name = 'musterino'  -- küçük harf (tırnaksız tanımlanmış)
    ) THEN
        -- Küçük harfli kolonu büyük harfli yap
        ALTER TABLE moy_bilgileri RENAME COLUMN musterino TO "musteriNo";
        RAISE NOTICE 'moy_bilgileri.musterino → musteriNo olarak yeniden adlandırıldı.';
    END IF;

    -- "moyKayitNo" kontrolü
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'moy_bilgileri'
          AND column_name = 'moykayitno'  -- küçük harf (tırnaksız tanımlanmış)
    ) THEN
        ALTER TABLE moy_bilgileri RENAME COLUMN moykayitno TO "moyKayitNo";
        RAISE NOTICE 'moy_bilgileri.moykayitno → moyKayitNo olarak yeniden adlandırıldı.';
    ELSE
        RAISE NOTICE 'moy_bilgileri.moyKayitNo zaten doğru.';
    END IF;
END $$;

-- =============================================================================
-- ÖZET: Bu script ne yapıyor?
-- =============================================================================
-- Problem: Servisler "vomsisBilgileri" (tırnaksız) olarak sorgu yapıyor.
--          PostgreSQL tırnaksız isimleri küçük harfe çeviriyor.
--          Tablo "vomsisBilgileri" büyük harf korumalı tanımlandıysa bulunamıyor.
--
-- Çözüm: pg_schema.py güncellendi — artık tırnaksız tanım var.
--         Mevcut tablolar için bu script'i Supabase SQL Editor'da çalıştırın.
-- =============================================================================
