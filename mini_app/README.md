# Flag Delay Mini App

Static HTML page opened by the "⚠️ Flag delay" button on the Telegram order card.
Displays a pre-formatted delay message and lets the user copy it to clipboard with one tap.

## Hosting on the droplet (nginx)

```bash
# Copy the file to nginx's web root
cp flag.html /var/www/html/flag.html

# If nginx isn't installed:
apt install nginx -y
systemctl enable nginx && systemctl start nginx
```

Then set `mini_app_base_url="http://<droplet-ip>/flag.html"` in `swiggy_listener_v2.py`.

## Alternatively — Python one-liner (no nginx)

```bash
cd /root/swiggy_order_svc/SwiggyOrderHooks/mini_app
python3 -m http.server 8080
```

Then use `http://<droplet-ip>:8080/flag.html`.
Make sure port 8080 is open in the droplet's firewall.

## Note on clipboard

`navigator.clipboard` requires either:
- HTTPS, or
- `localhost`

On plain HTTP, the page falls back to `document.execCommand("copy")` which works
in most mobile browsers. For full reliability, put the droplet behind an HTTPS
reverse proxy (Let's Encrypt + nginx is the easiest path).
