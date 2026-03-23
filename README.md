<p align="center">
  <img src="assert/atom-with-stars.png" width="120" alt="Atom Logo"/>
</p>

<h1 align="center">Atom — AI Research Digest Agent</h1>

<p align="center">
  Runs on laptop login · fetches arXiv papers · emails a daily digest
</p>

---

## Setup

```bash
bash Setup.sh
nano .env
```

**.env**
```
GMAIL_ADDRESS=you@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
RECIPIENT_EMAIL=you@wherever.com
```

---

## Usage

```bash
bash SetUp.sh
cat logs/digest.log   # check logs
```

---

## Customize

Edit `topics.json` to change what gets searched — no code changes needed.
