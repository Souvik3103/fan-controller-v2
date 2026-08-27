# Bambu A1 Fan Controller Dashboard v2

Features:
- Bambu MQTT monitoring
- Live printer activity/stage
- Manual/Bambu fan modes
- Custom hour/minute/second timer
- Resume/Pause/Stop controls
- Estimated finish time
- Temperature history with 15m/1h/6h/24h ranges
- Print history
- System monitoring
- Latest 10 scrollable events
- SQLite persistence
- systemd-friendly background operation

## Install

```bash
cd /home/souvikroy/fan-controller
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
```

Put your real Bambu values in `.env`.

## Run manually

```bash
source .venv/bin/activate
python3 app.py
```

Open:

http://<PI-IP>:5000

## systemd

Create:

`/etc/systemd/system/fan-controller.service`

Use the service file supplied with this project.

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now fan-controller
sudo systemctl status fan-controller
```

Logs:

```bash
journalctl -u fan-controller -f
```

## Important

Do not commit `.env` or the SQLite database.

Add to `.gitignore`:

```text
.env
data/fan.db
.venv/
__pycache__/
*.pyc
```
