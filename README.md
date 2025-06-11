#  Domain Impersonation Detection System

This project automates the detection of typosquatting campaigns by monitoring DNS changes of suspicious or similar domains, and sending alerts to a centralized security platform (e.g., Sekoia).

---

##  Requirements

### System Packages

Make sure the following are installed on your Linux environment:

```bash
sudo apt update && sudo apt install -y python3 python3-pip git cron curl
```

### Python Tooling

This project uses [Poetry](https://python-poetry.org/) for dependency and virtual environment management.

Install it with:

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

Make sure Poetry is available in your path (you may need to add `$HOME/.local/bin` to your `PATH`).

---

##  Directory Structure

```
DIDS/
├── config/
│   ├── tenants.json           # Contains tenant details and their intake keys
│
├── data/
│   └── previous_records.json  # Stores previous DNS states (auto-generated)
│
├── logs/                      # Temporary log output from checks
├── logs_old/                  # Processed logs moved here before sending
│
├── dns_check.py               # Python script to check for DNS and typosquatting changes
├── send_events.py             # Script to send alerts to the configured intake endpoints
├── events.sh                  # Main automation script
└── pyproject.toml             # Poetry project file
```

---

## ⚙️ Setup

You can install all required dependencies and create initial folders using the provided setup script:

```bash
./setup.sh
```

This script will:

* Create the `config/`, `data/`, and `logs/` folders
* Install system and Python dependencies
* Initialize `tenants.json` and `previous_records.json`

---

##  Configuration

### `config/tenants.json`

This file defines the tenants to monitor and the intake key for each. Example:

```json
[
  {
    "name": "OmniAccess",
    "main_domain": "omniaccess.com",
    "intake_key": "XXXXXXXXXXXXXXXXXXXXXX",
    "dtch": ["omnlaccess.com"],
    "dtch_generated": ["omnìaccess.com"]
  }
]
```

You must provide a unique `intake_key` per tenant.

---

##  Usage

### 1. Run the monitoring and alerting process

```bash
./events.sh
```

This will:

1. Move previous logs to `logs_old/`
2. Run the DNS and typosquatting check
3. Extract the tenant name from each log
4. Send each log to its corresponding intake endpoint using `send_events.py`

> You can schedule this script via `cron` to run periodically.

---

##  Example Crontab Entry

To run every 6 hours:

```cron
0 */6 * * * /path/to/your/project/events.sh >> /path/to/your/project/cron.log 2>&1
```

Make sure the script is executable:

```bash
chmod +x events.sh
```

---

##  Git Ignore

The following folders are ignored from version control:

```
logs/
data/
logs_old/
```

---

