import json
import os
import hashlib
from datetime import datetime, timezone
from pathlib import Path
import dns.resolver
import logging

# Constants
BASE_DIR = Path(__file__).resolve().parent
TENANTS_FILE = BASE_DIR / "config" / "tenants.json"
PREVIOUS_RECORDS_FILE = BASE_DIR / "data" / "previous_records.json"
SEKOIA_LOGS_DIR = BASE_DIR / "logs" / "sekoia"
SPLUNK_LOGS_DIR = BASE_DIR / "logs" / "splunk"
RECORD_TYPES = ["A", "MX", "NS"]


def load_tenants(filepath):
    with open(filepath, "r") as f:
        return json.load(f)


def load_previous_records(filepath):
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            return json.load(f)
    return {}


def save_previous_records(filepath, records):
    with open(filepath, "w") as f:
        json.dump(records, f, indent=2)


def setup_logger(tenant: str, to_sekoia: bool) -> logging.Logger:
    log_dir = SEKOIA_LOGS_DIR if to_sekoia else SPLUNK_LOGS_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{tenant.lower()}.log"

    logger = logging.getLogger(tenant)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.FileHandler(log_path, mode='a')  # Append mode
        formatter = logging.Formatter('%(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


def perform_lookup(domain, record_type):
    try:
        answers = dns.resolver.resolve(domain, record_type)
        return sorted([r.to_text() for r in answers])
    except Exception:
        return []


def generate_check_id(tenant, domain, record_type, timestamp):
    input_str = f"{tenant}{domain}{record_type}{timestamp}"
    return hashlib.md5(input_str.encode()).hexdigest()[:8]


def main():
    tenants = load_tenants(TENANTS_FILE)
    previous_records = load_previous_records(PREVIOUS_RECORDS_FILE)

    for tenant_info in tenants:
        tenant = tenant_info["name"]
        has_sekoia = "intake_key" in tenant_info
        dtch_list = tenant_info.get("dtch", [])
        generated_list = tenant_info.get("dtch_generated", [])
        main_domain = tenant_info.get("main_domain")
        all_domains = list(set([main_domain] + dtch_list + generated_list))

        logger = setup_logger(tenant, has_sekoia)

        for domain in all_domains:
            for record_type in RECORD_TYPES:
                current = perform_lookup(domain, record_type)
                prev = previous_records.get(tenant, {}).get(domain, {}).get(record_type, [])

                changed = current != prev
                timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
                check_id = generate_check_id(tenant, domain, record_type, timestamp)

                event = {
                    "timestamp": timestamp,
                    "tenant": tenant,
                    "domain_checked": domain,
                    "record_type": record_type,
                    "previous_value": prev,
                    "current_value": current,
                    "changed": changed,
                    "method": "DNS Lookup",
                    "check_id": check_id
                }

                logger.info(json.dumps(event))

                # Update the previous records
                previous_records.setdefault(tenant, {}).setdefault(domain, {})[record_type] = current

    save_previous_records(PREVIOUS_RECORDS_FILE, previous_records)


if __name__ == "__main__":
    main()

