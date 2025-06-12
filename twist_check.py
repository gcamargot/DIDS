import json
import subprocess
from pathlib import Path

TENANTS_FILE = "config/tenants.json"

def run_dnstwist(domain):
    """Run dnstwist and return list of registered variants."""
    try:
        result = subprocess.run(
            ["dnstwist", "--registered", "--format", "json", domain],
            capture_output=True,
            text=True,
            check=True
        )
        data = json.loads(result.stdout)
        registered = [
                entry["domain"].lower()
                for entry in data 
                if entry.get("dns_a") or entry.get("dns_ns") or entry.get("dns_mx")]
        return registered
    except subprocess.CalledProcessError as e:
        print(f"Error running dnstwist for {domain}: {e}")
        return []
    except json.JSONDecodeError:
        print(f"Error decoding dnstwist output for {domain}")
        return []

def update_tenants_with_variants(filepath):
    if not Path(filepath).exists():
        print(f"{filepath} not found.")
        return

    with open(filepath, "r") as f:
        tenants = json.load(f)

    for tenant in tenants:
        domain = tenant.get("main_domain")
        if not domain:
            print(f"Tenant {tenant.get('name')} missing 'main_domain'")
            continue

        print(f"Running dnstwist for {domain}...")
        registered_variants = run_dnstwist(domain)

        # Get existing dtch + dtch_generated
        manual_dtch = set(tenant.get("dtch", []))
        generated_dtch = set(tenant.get("dtch_generated", []))

        # Filter out any domains already present in either list
        filtered_variants = [
            d for d in registered_variants
            if d != domain and d not in manual_dtch and d not in generated_dtch
        ]

        tenant["dtch_generated"] = sorted(list(generated_dtch.union(filtered_variants)))
        print(f"  → {len(filtered_variants)} new variants added.")

    with open(filepath, "w") as f:
        json.dump(tenants, f, indent=2)

    print("Tenants updated with dtch_generated variants.")

# Run the update
update_tenants_with_variants(TENANTS_FILE)

