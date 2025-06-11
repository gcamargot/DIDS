import json
import os
import hashlib
from datetime import datetime
from pathlib import Path
import dns.resolver
import logging

# Constants
TENANTS_FILE = "config/tenants.json"
PREVIOUS_RECORDS_FILE = "data/previous_records.json"
LOGS_DIR = "logs"
RECORD_TYPES = ["A", "MX", "NS"]

# Load tenants
def load_tenants(filepath):
    with open(filepath, "r") as f:
        return json.load(f)

# Load previous DNS records
def load_previous_records(filepath):
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            return json.load(f)
    return {}

# Save updated DNS records
def save_previous_records(filepath, records):
    with open(filepath, "w") as f:
        json.dump(records, f, indent=2)

# Setup logger
def setup_logger(tenant):
    Path(LOGS_DIR).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M")
    log_filename = f"{LOGS_DIR}/{tenant.lower()}_{timestamp}.log"
    logger = logging.getLogger(tenant)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.FileHandler(log_filename)
        formatter = logging.Formatter('%(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger

# Perform DNS lookup
def perform_lookup(domain, record_type):
    try:
        answers = dns.resolver.resolve(domain, record_type)
        return sorted([r.to_text() for r in answers])
    except Exception:
        return []

# Generate check ID
def generate_check_id(tenant, domain, record_type, timestamp):
    input_str = f"{tenant}{domain}{record_type}{timestamp}"
    return hashlib.md5(input_str.encode()).hexdigest()[:8]

# Main function
def main():
    tenants = load_tenants(TENANTS_FILE)
    previous_records = load_previous_records(PREVIOUS_RECORDS_FILE)

    for tenant_info in tenants:
        tenant = tenant_info["name"]
        dtch_list = tenant_info.get("dtch", [])
        generated_list = tenant_info.get("dtch_generated", [])
        main_domain = tenant_info.get("main_domain")
        all_domains = list(set([main_domain] + dtch_list + generated_list))

        logger = setup_logger(tenant)

        for domain in all_domains:
            for record_type in RECORD_TYPES:
                current = perform_lookup(domain, record_type)
                prev = previous_records.get(tenant, {}).get(domain, {}).get(record_type, [])

                changed = current != prev
                timestamp = datetime.utcnow().isoformat() + "Z"
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

                # Update previous records if changed
                if tenant not in previous_records:
                    previous_records[tenant] = {}
                if domain not in previous_records[tenant]:
                    previous_records[tenant][domain] = {}
                previous_records[tenant][domain][record_type] = current

    save_previous_records(PREVIOUS_RECORDS_FILE, previous_records)

# Run the script
main()

