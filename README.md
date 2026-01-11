# Collect NEM Data from OpenElectricity

## Systemd Service Setup

Copy service file it into systemd:

```bash
sudo cp /home/tom/test_oe_api/open-electricity.service /etc/systemd/system/open-electricity.service
```

Reload units:

```bash
sudo systemctl daemon-reload
```

Enable on boot:

```bash
sudo systemctl enable open-electricity.service
```

Start now:

```bash
sudo systemctl start open-electricity.service
```

Check status/logs:

```bash
systemctl status open-electricity.service
journalctl -u open-electricity.service -n 100 --no-pager
```

Stop the service:

```bash
sudo systemctl stop open-electricity.service
```

Disable on boot:

```bash
sudo systemctl disable open-electricity.service
```

Restart after updating the scripts:

```bash
sudo systemctl restart open-electricity.service
```
