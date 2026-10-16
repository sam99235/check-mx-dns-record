# check_mx.py — Email domain MX validator

A small Python script that takes a list of email addresses and keeps only those
whose domain has a working **MX (mail exchanger) record**, which means the domain is
configured to receive email.

It works at the **domain level**: each unique domain is checked once, no matter
how many addresses use it.

---

## Requirements

- Python 3.8 or newer
- [dnspython](https://www.dnspython.org/)
- Outbound DNS access (UDP/TCP port 53) to your local or a public resolver

```bash
pip install dnspython
```

---

## Usage

```bash
python check_mx.py emails.txt
```

### Input format

Any plain-text file. The script extracts addresses with a regular expression, so
all of these layouts work and can be mixed:

```
a.name@example.ma,
contact@example.com

Company Name <info@example.net>,
```

Addresses are converted to lowercase and de-duplicated, keeping the first-seen
order.

---

## Output files

All files are written to the current working directory.

| File | Content |
|---|---|
| `valid_emails.txt` | One address per line: addresses whose domain has at least one real MX server |
| `invalid_emails.csv` | `email, domain, reason`: addresses whose domain is NXDOMAIN, NO_MX or NULL_MX |
| `retry_emails.csv` | `email, domain, reason`: addresses whose check failed because of a timeout or DNS error |
| `domains_report.csv` | `domain, status, mx_hosts, email_count`: one row per domain |

### Status codes

| Status | Meaning | Domain exists? | Accepts mail? | Action |
|---|---|---|---|---|
| `VALID` | At least one MX record points to a real host | Yes | Yes | Keep |
| `NO_MX` | Domain exists but publishes no MX record | Yes | Unlikely | Discard |
| `NULL_MX` | MX record is `.` (RFC 7505): domain explicitly refuses mail | Yes | No | Discard |
| `NXDOMAIN` | Domain does not exist in DNS | No | No | Discard |
| `ERROR` | Timeout or no nameserver answered (after 2 attempts) | Unknown | Unknown | Re-run |

> **About NO_MX:** RFC 5321 allows senders to fall back to the domain's A
> record when no MX exists. In practice this rarely works, so the script treats
> NO_MX as invalid. Check `domains_report.csv` if you want to review these
> domains by hand.

### Re-running failed lookups

`ERROR` results are temporary network problems, not proof that an address is
invalid. Re-run them later:

```bash
python check_mx.py retry_emails.csv
```

Running it again overwrites the output files, so rename or move the first
run's results beforehand.

---

## Configuration

Edit these values near the top of `check_mx.py`:

| Setting | Default | Purpose |
|---|---|---|
| `resolver.timeout` | `5` | Seconds to wait for one DNS server |
| `resolver.lifetime` | `10` | Total seconds allowed per query |
| `resolver.nameservers` | System resolver | Uncomment the line to use `8.8.8.8` / `1.1.1.1` instead |
| `max_workers` (in `main()`) | `20` | Number of parallel DNS lookups |

If you see many `ERROR` results, do the following:

- Lower `max_workers`.
- Switch to public resolvers.
- Check that a firewall or proxy isn't blocking DNS.

---

## Limitations

- **An MX record does not mean the mailbox exists.** A valid domain can still
  bounce mail for people who have left the organisation. Only a test send, or
  an SMTP `RCPT TO` check, can confirm a specific mailbox. Many servers block
  or falsify SMTP checks, so this script does not do them.
- **Legacy domains** of companies that have been renamed or acquired may still
  publish MX records while their mailboxes are no longer used.
- **Catch-all domains** accept every address, so their invalid mailboxes cannot
  be detected by DNS alone.
- **Results are a snapshot.** DNS records change over time.

---

## Windows alternative (PowerShell, no Python)

This version writes only `valid_emails.txt`:

```powershell
$emails = Select-String -Path emails.txt -Pattern '[\w.\-+%]+@[\w.\-]+\.\w{2,}' -AllMatches |
  ForEach-Object { $_.Matches.Value.ToLower() } | Sort-Object -Unique
$cache = @{}
$valid = foreach ($e in $emails) {
  $d = $e.Split('@')[1]
  if (-not $cache.ContainsKey($d)) {
    $cache[$d] = [bool](Resolve-DnsName $d -Type MX -ErrorAction SilentlyContinue |
      Where-Object { $_.Type -eq 'MX' -and $_.NameExchange -ne '.' })
  }
  if ($cache[$d]) { $e }
}
$valid | Set-Content valid_emails.txt
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `dnspython is missing` | `pip install dnspython` |
| Every domain shows `ERROR` | DNS is blocked. Try public resolvers or another network |
| `0 unique emails` | Check the input file path and encoding (UTF-8 recommended) |

---

## Data protection

These lists contain personal data, such as named individuals' work addresses.
In Morocco, processing personal data and sending unsolicited direct marketing
by email are governed by **Law 09-08** and overseen by the **CNDP**. Prior
consent is generally required. Store the input and output files securely, and
delete them when they are no longer needed.
