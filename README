# 🎵 Music Text Converter

**Music Text Converter** — bu loyiha foydalanuvchilarga ikki asosiy xizmatni taqdim etadi:

- 🎙️ **Media to Text** — Audio/video fayllarni matnga aylantirish
- 🗣️ **Text to Audio** — Matnni erkak yoki ayol ovozda audio faylga aylantirish

---

## 🏗️ Tizim Arxitekturasi

Loyiha **mikroservis arxitekturasi** asosida ishlab chiqilgan:

| Servis           | Texnologiya               | Port     |
|------------------|---------------------------|----------|
| 🌀 API Gateway    | FastAPI                   | `8000`   |
| 🎧 Media Processor| FastAPI + OpenAI Whisper  | `8001`   |
| 🔊 Text-to-Speech | FastAPI + gTTS/pyttsx3    | `8002`   |
| 🗃️ PostgreSQL     | Ma'lumotlar bazasi        | `5432`   |
| ⚡ Redis          | Kesh va navbat            | `6379`   |
| ☁️ MinIO          | Fayl saqlash (S3-compatible) | `9000/9001` |

---

## 🚀 Tez Boshlash

### 1. Talab qilinadigan dasturlar
- Docker
- Docker Compose
- Make (ixtiyoriy)

### 2. Loyihani klonlash
```bash
git clone <repository-url>
cd music_txt_changer
