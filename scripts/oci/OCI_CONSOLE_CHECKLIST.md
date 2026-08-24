# Oracle Cloud Console Checklist

Complete these steps in the [Oracle Cloud Console](https://cloud.oracle.com/) before running `bootstrap-vm.sh` on the VM.

## 1. Create Always Free account

- Sign up: https://www.oracle.com/cloud/free/
- Choose a **home region** near participants (e.g. `ap-mumbai-1` for India)
- Complete identity verification

## 2. Create VM instance

**Compute → Instances → Create instance**

| Field | Value |
|-------|-------|
| Name | `tradeverse` |
| Compartment | (default or create one) |
| Image | Ubuntu 22.04 LTS |
| Shape | `VM.Standard.A1.Flex` (Ampere, **Always Free-eligible**) |
| OCPUs | **2** |
| Memory | **12 GB** |
| Boot volume | ≤ 200 GB |
| Networking | Assign **public IPv4** |
| SSH keys | Paste your **public** key |

> If Ampere capacity is unavailable, retry another availability domain or off-peak hours.

## 3. Security list (ingress rules)

**Networking → Virtual cloud networks → your VCN → Security Lists → Default**

Add ingress rules:

| Source | Protocol | Port | Description |
|--------|----------|------|-------------|
| `0.0.0.0/0` | TCP | 22 | SSH |
| `0.0.0.0/0` | TCP | 80 | HTTP (certbot + redirect) |
| `0.0.0.0/0` | TCP | 443 | HTTPS / WSS |

**Do not** open 5432, 8000, or 3000.

## 4. Note your public IP

After the instance is **Running**, copy the **public IP address**.

Convert to sslip.io hostname:

```bash
./scripts/oci/sslip-hostname.sh YOUR_PUBLIC_IP
# e.g. 203.0.113.10 → 203-0-113-10.sslip.io
```

## 5. SSH into the VM

```bash
ssh -i ~/.ssh/your_key ubuntu@YOUR_PUBLIC_IP
```

## 6. Run bootstrap on the VM

```bash
curl -fsSL https://raw.githubusercontent.com/ragingbul/mock-stock-exchange/main/scripts/oci/bootstrap-vm.sh | bash
```

Or after cloning:

```bash
cd ~/tradeverse
./scripts/oci/configure-env.sh YOUR_PUBLIC_IP
./scripts/oci/setup-letsencrypt.sh YOUR_PUBLIC_IP
./scripts/oci/deploy.sh
./scripts/oci/verify-deployment.sh --load-test
```

## Cost guardrails

- Use **Always Free** shapes only — do not enable paid load balancers or managed DB
- Stay within 2 OCPU / 12 GB Ampere allocation (2026 Always Free limit)
- All services run on one VM via Docker — no extra paid resources needed
