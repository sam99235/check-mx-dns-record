#!/usr/bin/env python3
"""
check_mx.py - Validate email addresses by checking their domain's MX records.

Usage:
    pip install dnspython
    python check_mx.py emails.txt

Input : any text file containing email addresses (commas, newlines,
        "Name <email>" formats are all handled).
Output (in the current folder):
    valid_emails.txt     -> emails whose domain has at least one real MX server
    invalid_emails.csv   -> email, domain, reason  (NXDOMAIN / NO_MX / NULL_MX)
    retry_emails.csv     -> email, domain, reason  (timeouts / DNS errors - rerun these)
    domains_report.csv   -> domain, status, mx_hosts, email_count

Note: an MX record proves the DOMAIN accepts mail, not that the specific
mailbox (e.g. a person who left the company) still exists.
"""

import csv
import re
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import dns.resolver
    import dns.exception
except ImportError:
    sys.exit("dnspython is missing. Install it with:  pip install dnspython")

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

resolver = dns.resolver.Resolver()
resolver.timeout = 5
resolver.lifetime = 10
# Uncomment to force public resolvers if your local DNS is unreliable:
# resolver.nameservers = ["8.8.8.8", "1.1.1.1"]


def check_domain(domain):
    """Return (status, mx_hosts). Status is one of:
    VALID, NO_MX, NXDOMAIN, NULL_MX, ERROR"""
    for attempt in range(2):
        try:
            answers = resolver.resolve(domain, "MX")
            hosts = sorted(
                (r.preference, str(r.exchange).rstrip(".")) for r in answers
            )
            real = [h for _, h in hosts if h not in ("", ".")]
            if not real:
                return "NULL_MX", ""          # RFC 7505: domain refuses mail
            return "VALID", " ".join(real)
        except dns.resolver.NXDOMAIN:
            return "NXDOMAIN", ""             # domain does not exist
        except dns.resolver.NoAnswer:
            return "NO_MX", ""                # domain exists but has no MX
        except (dns.resolver.NoNameservers, dns.exception.Timeout) as e:
            last_err = type(e).__name__
        except Exception as e:                # any other DNS problem
            last_err = type(e).__name__
    return "ERROR", last_err


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: python check_mx.py emails.txt")

    with open(sys.argv[1], encoding="utf-8", errors="ignore") as f:
        text = f.read()

    # Extract, normalise, dedupe (keep first-seen order)
    seen, emails = set(), []
    for e in EMAIL_RE.findall(text):
        e = e.strip().strip(".").lower()
        if e not in seen:
            seen.add(e)
            emails.append(e)

    by_domain = defaultdict(list)
    for e in emails:
        by_domain[e.split("@", 1)[1]].append(e)

    print(f"{len(emails)} unique emails across {len(by_domain)} domains. Checking MX...")

    results = {}
    with ThreadPoolExecutor(max_workers=20) as pool:
        futures = {pool.submit(check_domain, d): d for d in by_domain}
        for i, fut in enumerate(as_completed(futures), 1):
            d = futures[fut]
            results[d] = fut.result()
            print(f"[{i}/{len(by_domain)}] {d:40s} {results[d][0]}")

    valid, invalid, retry = [], [], []
    for e in emails:
        d = e.split("@", 1)[1]
        status, info = results[d]
        if status == "VALID":
            valid.append(e)
        elif status == "ERROR":
            retry.append((e, d, info))
        else:
            invalid.append((e, d, status))

    with open("valid_emails.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(valid) + ("\n" if valid else ""))

    for name, rows in (("invalid_emails.csv", invalid), ("retry_emails.csv", retry)):
        with open(name, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["email", "domain", "reason"])
            w.writerows(rows)

    with open("domains_report.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["domain", "status", "mx_hosts", "email_count"])
        for d in sorted(by_domain):
            status, info = results[d]
            w.writerow([d, status, info, len(by_domain[d])])

    print("\nDone.")
    print(f"  Valid (has MX) : {len(valid)}  -> valid_emails.txt")
    print(f"  Invalid        : {len(invalid)}  -> invalid_emails.csv")
    print(f"  DNS errors     : {len(retry)}  -> retry_emails.csv (rerun later)")
    print("  Per-domain     : domains_report.csv")


if __name__ == "__main__":
    main()
