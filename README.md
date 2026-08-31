# 🦀 Claw Royale Bot v6.1 - Super Hybrid AI

[![Python Version](https://img.shields.io/badge/python-3.11-blue.svg)](https://python.org)
[![Railway](https://img.shields.io/badge/deploy-Railway-0B0D0E.svg)](https://railway.app)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Bot otomatis untuk Claw Royale dengan **Super Hybrid Strategy** (4 Mode: Beatdown, Control, Bridge Spam, Siege) + Reinforcement Learning.

---

## ✨ **Fitur Unggulan**

### 🔥 **Super Hybrid Strategy (4 Mode)**
| Mode | Deskripsi |
|------|-----------|
| **Beatdown** | Big push, clear everything |
| **Control** | Defensive, chip damage |
| **Bridge Spam** | Aggressive, constant pressure |
| **Siege** | Safe, consistent damage |

### 🤖 **AI Engine**
- Hybrid AI + Reinforcement Learning
- Smart mode selector berdasarkan situasi
- Adaptive decision making

### 🎮 **Game Features**
- Auto-join free/paid rooms
- Auto-rejoin after timeout
- Auto-restart after death
- Ruin farming with alert management
- Guardian avoidance
- Item tracking & validation
- Auto-use healing items
- Auto-equip best items

### 📊 **Monitoring**
- Health check (`/health`)
- Metrics (`/metrics`)
- Stats (`/stats`)
- Dashboard (`/dashboard`)

---

## 🚀 **Quick Start**

```bash
# Clone
git clone https://github.com/username/claw-royale-bot.git
cd claw-royale-bot

# Setup
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp config/.env.example .env
# Edit .env dengan CLAW_API_KEY

# Run
python -m src.main