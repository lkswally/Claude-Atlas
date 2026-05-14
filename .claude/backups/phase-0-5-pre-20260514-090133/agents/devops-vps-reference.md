# DevOps VPS — Referencia (validado en producción con Oracle Cloud)

Referencia técnica para deploy en VPS (Oracle Cloud, AWS EC2, DigitalOcean, etc.).
Solo relevante cuando el proyecto se deploya en VPS — no cuando se usa Vercel/Netlify.

## Mixed Content HTTPS — static site HTTPS + backend HTTP
Browsers bloquean TODAS las requests HTTP desde páginas HTTPS. Afecta `fetch()`, `img src`, `video src`, `XMLHttpRequest`.

**Soluciones (de más simple a más permanente)**:
1. **nginx + Let's Encrypt** (requiere puertos 80/443 accesibles + dominio): Permanente, sin dependencias externas. Usar `sslip.io` si no hay dominio propio: `161-153-203-83.sslip.io` resuelve a `161.153.203.83`.
2. **Cloudflare Quick Tunnel** (sin cuenta ni dominio): `cloudflared tunnel --url http://localhost:PORT` → URL `*.trycloudflare.com`. Cambio en cada restart — solo para fix temporal.
3. **Cloudflare Named Tunnel** (requiere cuenta + dominio): Permanente, conecta outbound, no necesita puertos abiertos en el firewall.

## Oracle Cloud Free Tier — Dos capas de firewall independientes
Oracle tiene DOS firewalls que **ambos** deben permitir el puerto:
- **Capa 1 — UFW** (dentro de la VM, configurable vía SSH): `sudo ufw allow 80/tcp`
- **Capa 2 — VCN Security List** (nivel de red, solo en Oracle Cloud console): Networking → VCNs → Security Lists → Add Ingress Rule → CIDR `0.0.0.0/0`, TCP, puerto
- **Diagnóstico**: si `ufw allow` no sirve → es VCN. Test: `curl http://IP:PORT` desde fuera — si da 000 (timeout), es VCN; si da error de conexión, es UFW.
- **Workaround sin tocar VCN**: Cloudflare Tunnel (conecta outbound, no necesita inbound ports)

## nginx como reverse proxy + Let's Encrypt
```bash
sudo apt-get install -y nginx certbot python3-certbot-nginx
sudo certbot --nginx -d MI-DOMINIO.sslip.io --non-interactive --agree-tos -m email@example.com
```
