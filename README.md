# hsmaker

无需vps回家方案，适用于家宽没有公网IP，但具属于NAT1类型。

## cloudflare权限
- Zone - Origin Rules - Edit
- Zone - Zone - Read
- Zone - DNS - Edit

## 功能
- 支持双栈自动切换，最大程度保障回家链路稳定性，确保各种环境下都能顺利接入
- 自动更新打洞IP和端口信息
- Headscale 和Derp证书统一由traefik反代接管，减少打洞端口数量
- 自动同步traefik生成的证书给derp使用
- 自动监测ipv6地址变化，并同步更新
- ipv6防火墙仅开放derp端口和stun端口
