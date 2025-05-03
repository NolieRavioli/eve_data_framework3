# EVE Data Framework 3

**EVE Data Framework 3** is a modular and scalable backend system built for interacting with the EVE Online ESI API. 
It provides authentication, persistent databases, asset fetching, industry job tracking, skill management, and more.

<ol type='1'>
<a href="#-features"><li>✨ Features</li></a>
<a href="#-project-structure"><li>📂 Project Structure</li></a>
<a href="#%EF%B8%8F-quickstart"><li>⚙️ Quickstart</li></a>
<ol>
<a href="#1-install-requirements"><li>Install Requirements</li></a>
<a href="#2-configure-environment"><li>Configure Environment</li></a>
<a href="#3-run-the-app"><li>Run the App</li></a>
</ol>
<a href="#-security"><li>🔒 Security</li></a>
<a href="#%EF%B8%8F-system-principles"><li>🛠️ System Principles</li></a>
<a href="#-fetchers"><li>🚀 Fetchers</li></a>
<ol>
<a href="#private-toon-fetchers"><li>Private Toon Fetchers</li></a>
<a href="#public-fetchers"><li>Public Fetchers</li></a>
</ol>
<a href="#-future-roadmap"><li>📖 Future Roadmap</li></a>
<a href="#-development-notes"><li>🧹 Development Notes</li></a>
<a href="#-contributing"><li>🤝 Contributing</li></a>
<a href="#%EF%B8%8F-license"><li>🛡️ License</li></a>
<a href="#-made-with--by-nolan"><li>✨ Made with ♥ by Nolan</li></a>
</ol>

---

## ✨ Features

- Full OAuth2 SSO Login & Token Refresh
- Secure, Encrypted Credential Storage
- Persistent Character (Toon) Databases (Private/Public Separation)
- Public and Private Data Storage (Market vs Personal Data)
- Periodic Background Data Fetching (Assets, Industry, Skills, Wallets, etc.)
- Auto-Migration of Database Schemas
- Built-in Flask WebUI for Overview and Control
- Config YAML Auto-Updating (Character Tracking)
- Auto-install of Missing Dependencies
- Robust Error Handling and Token Recovery
- Extensible Fetcher and Analysis Framework
- Production-Grade Modular Architecture

---

## 📂 Project Structure
```plaintext
eve_data_framework3/    
├── _privateData/           # Per-owner SQLite databases (private toon data)  
├── _publicData/            # Shared public database (e.g., contracts)  
├── _sde/                   # Static Data Exports (EVE types, stations)  
├── analysis/               # Analysis modules (e.g., job_slots)  
├── db/                     # Database Initialization, Models.  
├── esi/					# Private Data Fetch Modules. Personal toon data (assets, skills, wallet, etc.)  
│   └── public/             # Public Data Fetch Modules market and structure info  
├── util/                   # Helpers: Auth, SDE, Utils  
├── webUI/                  # Flask WebUI, routes, and logic  
├── !getstruct.py           # Dev tool for project structure output  
├── scheduler.py            # (Future) Background Task Orchestrator  
├── main.py                 # Main App Starter  
├── requirements.txt        # Python Requirements  
├── config.yaml             # Config file for env variables  
├── README.md               # This File  
└── LICENCE.md              # License Information (MIT)  
```

---

## ⚙️ Quickstart

### 1. Install Requirements

```shell
pip install -r requirements.txt
```
Or just let `main.py` auto-install them if missing.

### 2. Configure Environment

Modify `config.yaml` if you want to predefine regions, structures, or characters.

### 3. Run the App

```shell
python main.py
```

This will:
- Load your config and environment
- Initialize public and private databases
- Launch the local Flask WebUI (http://127.0.0.1:5000)

First auth will guide you through secure credential setup.

---

## 🔒 Security

> **⚠️WARNING!** HTTPS/secure transport is NOT enforced — this is a lightweight dev-grade system. Planned usage is with a reverse proxy.

- Client credentials are encrypted using **Fernet AES256**.
- OAuth2 tokens are automatically refreshed when expired.
- SQLite private toon databases are isolated by owner_id.
- Tokens validated against EVE SSO JWKS (auto-failsafe refresh).

---

## 🛠️ System Principles

- **Modular**: Every component handles one responsibility cleanly.
- **Scalable**: Supports multiple characters and multi-owner expansion.
- **Persistent**: No data lost across crashes or reboots.
- **Extensible**: Easy to add new fetchers, routes, or analyses.
- **Production-Ready**: Structured separation of concerns, clean error handling.

---

## 🚀 Fetchers

### Private Toon Fetchers
- Personal Assets
- Personal Bookmarks
- Corporate Bookmarks
- Personal Industry Jobs
- Personal Skills and Skill Queue
- Personal Wallet Journal

### Public Fetchers
- Public Market Contracts (Region by Region)
- Station and Structure Info (Coming soon)
- Static Data Helpers (SDE loading)

---

## 📖 Future Roadmap

- 🎯 Industry Job Slot Analysis and Visualization
- 📦 Production Pipeline Mapping
- 📈 Wallet History Graphs
- 🗺️ In-Game Route Finder (System Graphs)
- 🔔 Alerts for Industry Completions (Email, Discord)
- ⚡ Async Fetcher and Job Processing (Background Workers)

---

## 🧹 Development Notes

- Database tables auto-create on startup if missing.
- Public and Private database separation ensures minimal cross-locks.
- Error-prone issues like `DetachedInstanceError` are avoided by scoped sessions.

---

## 🤝 Contributing

Pull requests are very welcome!  
Please follow modular design principles and clear logging practices.  
For larger changes, open an issue first to discuss design alignment.

---

## 🛡️ License

This project is licensed under the **MIT License**.  
See `LICENCE.md` for details.

---

## ✨ Made with ♥ by Nolan
```plaintext
eve_data_framework3/  
├── analysis/  
│   ├── job_slots.py  
│   └── structures.py  
├── db/  
│   ├── database.py  
│   └── models.py  
├── esi/  
│   ├── public/  
│   │   ├── market_contracts.py  
│   │   ├── market_station.py  
│   │   ├── market_structure.py  
│   │   └── static_data.py  
│   ├── corp_bookmarks.py  
│   ├── personal_assets.py  
│   ├── personal_bookmarks.py  
│   ├── personal_industry_jobs.py  
│   ├── personal_skills.py  
│   └── personal_wallet.py  
├── util/  
│   ├── auth.py  
│   ├── sde.py  
│   └── utils.py  
├── webUI/  
│   ├── templates/  
│   │   ├── dashboard.html  
│   │   └── market_browser.html  
│   ├── __init__.py  
│   ├── app.py  
│   ├── dashboard.py  
│   ├── market_browser.py  
│   ├── personal_routes.py  
│   ├── public_routes.py  
│   └── sso.py  
├── !getstruct.py  
├── .gitignore  
├── LICENCE.md  
├── README.md  
├── config.yaml  
├── main.py  
└── requirements.txt
```