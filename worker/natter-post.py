#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @Project : tools
# @File : natter-post.py
# @Software: PyCharm
# @Author : 易雾君
# @Email : evling2020@gmail.com
# @公众号 : 易雾山庄
# @Site : https://www.evling.tech
# @Describe : 家庭基建，生活乐享. 
# @Time : 2024/11/17 01:01

import urllib.request
import json
import sys
import ipaddress
import netifaces
import time
import os
import subprocess
import yaml
import base64
import schedule
# Natter notification script arguments

class NatterPost():
    def __init__(self):
        self.cf_master_host = os.environ.get('CF_MASTER_DOMAIN').strip()
        self.cf_slave_hosts = [x.strip() for x in os.environ.get('CF_SLAVE_DOMAINS').split(',')]
        self.derp_file = "/etc/headscale/derp.yaml"
        self.derp_domain = os.getenv("DERP_DOMAIN").strip()
        self.derp_stun_port = int(os.getenv("DERP_STUN_PORT").strip())
        self.traefik_websecure_port = int(os.getenv("TRAEFIK_WEBSECURE_PORT").strip())
        self.cf_auth_key = self.read_secret('cf_api_token')
        self.acme_json_file = "/app/certs/acme.json"
        self.derp_dir = "/app/certs"

    def read_secret(self, secret_name):
        secret_path = f"/run/secrets/{secret_name}"
        try:
            with open(secret_path, "r") as file:
                return file.read().strip()
        except FileNotFoundError:
            raise RuntimeError(f"Secret {secret_name} not found in {secret_path}")

    def is_public_ipv6(self, ip):
        try:
            # 转换为 IPv6 对象
            ipv6 = ipaddress.IPv6Address(ip)
            # 排除私有地址范围
            return not (
                    ipv6.is_link_local or  # 链路本地地址
                    ipv6.is_site_local or  # 站点本地地址
                    ipv6.is_private  # ULA
            )
        except ipaddress.AddressValueError:
            return False

    def get_public_ipv6_address(self):
        # 获取所有接口
        interfaces = netifaces.interfaces()
        for interface in interfaces:
            addresses = netifaces.ifaddresses(interface)
            # 检查是否有 IPv6 地址
            if netifaces.AF_INET6 in addresses:
                for addr_info in addresses[netifaces.AF_INET6]:
                    ipv6_address = addr_info.get('addr', '').split('%')[0]  # 获取 IPv6 地址，去掉范围标识符
                    if self.is_public_ipv6(ipv6_address):
                        # Logger.info(f"当前IPv6 地址是: {ipv6_address}")
                        return ipv6_address
        return None

    def update_ipv4_address(self, update_derp_only=False):
        protocol, private_ip, private_port, public_ip, public_port = sys.argv[1:6]
        if not os.path.exists(self.derp_file):
            yaml_data = {
                'regions':{
                    900:{
                        'regionid': 900,
                        'regioncode': 'cn',
                        'regionname': 'China',
                        'nodes':[{
                            'hostname': self.derp_domain,
                            'name': '900a',
                            'regionid': 900,
                            'stunonly': False
                        }]
                    }
                }
            }
        else:
            with open(self.derp_file, "r") as file:
                yaml_data = yaml.safe_load(file)  # 加载为 Python 字典
                file.close()

        if not update_derp_only and protocol == "tcp":
            Logger.info("Updating Cloudflare info")
            cf = CloudFlareOrigin(self.cf_auth_key)
            Logger.info(f"Setting [ {self.cf_master_host} ] DNS to [ {public_ip} ] proxied by CloudFlare...")
            cf.set_a_record(self.cf_master_host, public_ip, proxied=True)
            Logger.info(f"Setting origin rules : [ {self.cf_master_host}, {', '.join(self.cf_slave_hosts)} ]")
            cf.set_origin_rule(self.cf_master_host, self.cf_slave_hosts, public_port)

        Logger.info("Updating ipv4 derp info")
        yaml_data['regions'][900]['nodes'][0]['ipv4'] = public_ip
        yaml_data['regions'][900]['nodes'][0]["derpport" if protocol=="tcp" else "stunport"] = int(public_port)
        yaml_data['regions'][900]['nodes'][0]['hostname'] = self.derp_domain
        with open(self.derp_file, "w") as file:
            yaml.dump(yaml_data, file, default_flow_style=False, allow_unicode=True)
            file.close()

    def update_ipv6_address(self, force_update=False):
        ipv6_address = self.get_public_ipv6_address()
        # if ipv6_address is None:
        #     return
        if not os.path.exists(self.derp_file):
            yaml_data = {
                'regions':{
                    900:{
                        'regionid': 900,
                        'regioncode': 'cn',
                        'regionname': 'China',
                        'nodes':[{
                            'hostname': self.derp_domain,
                            'name': '900a',
                            'regionid': 900,
                            'stunonly': False
                        }]
                    }
                }
            }
        else:
            with open(self.derp_file, "r") as file:
                yaml_data = yaml.safe_load(file)  # 加载为 Python 字典
                file.close()
        # if ipv6_address is None and len(yaml_data['regions'][900]['nodes']) > 1 and yaml_data['regions'][900]['nodes'][1].get('ipv6') is None:
        #     return
        if not force_update and len(yaml_data['regions'][900]['nodes']) > 1 and yaml_data['regions'][900]['nodes'][1].get(
                'ipv6') == ipv6_address:
            # Logger.info("IPv6地址没有变化，不做更新")
            return False
        cf = CloudFlareOrigin(self.cf_auth_key)
        if ipv6_address:
            Logger.info(f"Updating Derp IPv6 address: {ipv6_address}")
            to_add_item = {
                'derpport': self.traefik_websecure_port,
                'hostname': self.derp_domain,
                'ipv6': ipv6_address,
                'name': '900b',
                'regionid': 900,
                'stunonly': False,
                'stunpot': self.derp_stun_port
            }
            if len(yaml_data['regions'][900]['nodes']) == 1:
                yaml_data['regions'][900]['nodes'].append(to_add_item)
            else:
                yaml_data['regions'][900]['nodes'][1].update(to_add_item)
            with open(self.derp_file, "w") as file:
                yaml.dump(yaml_data, file, default_flow_style=False, allow_unicode=True)
                file.close()
            Logger.info("Updating Cloudflare info")
            Logger.info(f"Setting [ {self.cf_master_host} ] DNS to [ {ipv6_address} ] proxied by CloudFlare...")
            cf.set_a_record(self.cf_master_host, ipv6_address, proxied=True, type="AAAA")
            if self.traefik_websecure_port != 443:
                Logger.info(f"Setting origin rules : [ {self.cf_master_host}, {', '.join(self.cf_slave_hosts)} ]")
                cf.set_origin_rule(self.cf_master_host, self.cf_slave_hosts, self.traefik_websecure_port)
            else:
                Logger.info(f"Deleting origin rules")
                cf.del_origin_rule(self.cf_master_host)

        else:
            if len(yaml_data['regions'][900]['nodes']) > 1 and yaml_data['regions'][900]['nodes'][1].get('ipv6'):
                Logger.info(f"Removing Derp IPv6 address")
                yaml_data['regions'][900]['nodes'].pop(1)
                with open(self.derp_file, "w") as file:
                    yaml.dump(yaml_data, file, default_flow_style=False, allow_unicode=True)
                    file.close()
                ## 回退降级至ipv4端口暴露
                public_ip = yaml_data['regions'][900]['nodes'][0]['ipv4']
                public_port = yaml_data['regions'][900]['nodes'][0]['derpport']
                Logger.info(f"Setting [ {self.cf_master_host} ] DNS to [ {public_ip} ] proxied by CloudFlare...")
                cf.set_a_record(self.cf_master_host, public_ip, proxied=True)
                Logger.info(f"Setting origin rules : [ {self.cf_master_host}, {', '.join(self.cf_slave_hosts)} ]")
                cf.set_origin_rule(self.cf_master_host, self.cf_slave_hosts, public_port)
            else:
                return False
        Logger.info("ipv6 nftables setting ...")
        try:
            result = subprocess.check_output(
                ["nft"] + ["list chain ip6 filter input_natter"],
                stderr=subprocess.STDOUT
            ).decode()
            subprocess.check_output(['nft'] + ["delete chain ip6 filter input_natter"])
        except subprocess.CalledProcessError:
            pass
        subprocess.check_output(
            ['nft'] + ["add chain ip filter forward { type filter hook forward priority 0; policy accept; }"])
        subprocess.check_output(['nft'] + ["add table ip6 filter"])
        # subprocess.check_output(["nft"] + ["add chain ip6 nat NATTER"])
        subprocess.check_output(
            ["nft"] + ["add chain ip6 filter input_natter { type filter hook input priority 0; policy drop;}"])
        subprocess.check_output(['nft'] + ["add rule ip6 filter input_natter ct state {established,related} accept"])
        subprocess.check_output(['nft'] + ["add rule ip6 filter input_natter iifname lo accept"])
        subprocess.check_output(
            ["nft"] + [f"add rule ip6 filter input_natter tcp dport {self.traefik_websecure_port} accept"])
        subprocess.check_output(["nft"] + [f"add rule ip6 filter input_natter udp dport {self.derp_stun_port} accept"])
        subprocess.check_output(["nft"] + [
            "add rule ip6 filter input_natter icmpv6 type { echo-request, echo-reply, nd-router-solicit, nd-router-advert, nd-neighbor-solicit, nd-neighbor-advert } accept"])

        return True

    # 读取 acme.json 文件
    def read_acme_json(self, json_path):
        if os.path.exists(json_path):
            with open(json_path, 'r') as file:
                try:
                    content = json.load(file)
                except:
                    file.close()
                    return None
                file.close()
            return content
        else:
            return None

    # Base64 解码
    def base64_decode(self, data):
        return base64.b64decode(data)

    # 读取现有的 PEM 文件内容
    def read_pem_file(self, pem_path):
        if os.path.exists(pem_path):
            with open(pem_path, 'rb') as pem_file:
                content = pem_file.read()
                pem_file.close()
            return content
        return None

    # 校验证书或私钥是否有变化
    def has_certificate_changed(self, existing_cert_path, new_cert_data):
        existing_cert_data = self.read_pem_file(existing_cert_path)
        return existing_cert_data != new_cert_data

    # 提取证书和私钥，并同步到 derp 目录
    def sync_certificates(self, acme_json_path, derp_dir, domain):
        derp_domain = domain
        common_domin = '*.' + '.'.join(domain.split('.')[1:])
        acme_data = self.read_acme_json(acme_json_path)
        if acme_data is None:
            return
        certificates = acme_data.get('cfresolver', {}).get('Certificates', [])
        if not certificates:
            Logger.warning("未找到证书信息！")
            return
        for cert in certificates:
            temp_domains = list()
            if cert.get('domain', {}).get('main', None):
                temp_domains.append(cert.get('domain').get('main'))
            if cert.get('domain', {}).get('sans', []):
                temp_domains.extend(cert.get('domain').get('sans'))
            if derp_domain not in temp_domains and common_domin not in temp_domains:
                continue
            cert_data = cert.get('certificate')
            key_data = cert.get('key')
            if cert_data and key_data:
                # 解码证书和私钥
                decoded_cert = self.base64_decode(cert_data)
                decoded_key = self.base64_decode(key_data)
                # 定义证书和私钥的保存路径
                cert_path = os.path.join(derp_dir, f"{derp_domain}.crt")
                key_path = os.path.join(derp_dir, f"{derp_domain}.key")
                # 只有在证书或私钥有变化时才进行同步
                cert_changed = self.has_certificate_changed(cert_path, decoded_cert)
                key_changed = self.has_certificate_changed(key_path, decoded_key)
                if cert_changed or key_changed:
                    # 将证书写入 PEM 文件
                    with open(cert_path, 'wb') as cert_file:
                        cert_file.write(decoded_cert)
                        cert_file.close()
                    # 将私钥写入 PEM 文件
                    with open(key_path, 'wb') as key_file:
                        key_file.write(decoded_key)
                        key_file.close()
                    Logger.info(f"证书已同步到 {cert_path}")
                    Logger.info(f"私钥已同步到 {key_path}")
                # else:
                #     Logger.info("证书和私钥未发生变化，跳过同步。")
            else:
                Logger.error("证书或私钥数据缺失！")
            break

    def run_schedule(self):
        while True:
            schedule.run_pending()
            time.sleep(5)

class Logger(object):
    DEBUG = 0
    INFO  = 1
    WARN  = 2
    ERROR = 3
    rep = {DEBUG: "D", INFO: "I", WARN: "W", ERROR: "E"}
    level = INFO
    if "256color" in os.environ.get("TERM", ""):
        GREY = "\033[90;20m"
        YELLOW_BOLD = "\033[33;1m"
        RED_BOLD = "\033[31;1m"
        RESET = "\033[0m"
    else:
        GREY = YELLOW_BOLD = RED_BOLD = RESET = ""

    @staticmethod
    def set_level(level):
        Logger.level = level

    @staticmethod
    def debug(text=""):
        if Logger.level <= Logger.DEBUG:
            sys.stderr.write((Logger.GREY + "%s [%s] %s\n" + Logger.RESET) % (
                time.strftime("%Y-%m-%d %H:%M:%S"), Logger.rep[Logger.DEBUG], text
            ))

    @staticmethod
    def info(text=""):
        if Logger.level <= Logger.INFO:
            sys.stderr.write(("%s [%s] %s\n") % (
                time.strftime("%Y-%m-%d %H:%M:%S"), Logger.rep[Logger.INFO], text
            ))

    @staticmethod
    def warning(text=""):
        if Logger.level <= Logger.WARN:
            sys.stderr.write((Logger.YELLOW_BOLD + "%s [%s] %s\n" + Logger.RESET) % (
                time.strftime("%Y-%m-%d %H:%M:%S"), Logger.rep[Logger.WARN], text
            ))

    @staticmethod
    def error(text=""):
        if Logger.level <= Logger.ERROR:
            sys.stderr.write((Logger.RED_BOLD + "%s [%s] %s\n" + Logger.RESET) % (
                time.strftime("%Y-%m-%d %H:%M:%S"), Logger.rep[Logger.ERROR], text
            ))

class CloudFlareOrigin:
    def __init__(self, auth_key):
        self.opener = urllib.request.build_opener()
        self.opener.addheaders = [
            # ("X-Auth-Email",    auth_email),
            ("Authorization", f"Bearer {auth_key}"),
            ("Content-Type",    "application/json")
        ]

    def set_a_record(self, name, ipaddr, proxied=False, type="A"):
        zone_id = self._find_zone_id(name)
        if not zone_id:
            raise ValueError("%s is not on CloudFlare" % name)
        rec_id = self._find_a_record(zone_id, name)
        if not rec_id:
            rec_id = self._create_a_record(zone_id, name, ipaddr, proxied, type=type)
        else:
            rec_id = self._update_a_record(zone_id, rec_id, name, ipaddr, proxied, type=type)
        return rec_id

    def set_origin_rule(self, master_domain, slave_domains, public_port):
        zone_id = self._find_zone_id(master_domain)
        ruleset_id = self._get_origin_ruleset(zone_id)
        rule_id = self._find_origin_rule(zone_id, ruleset_id, master_domain)
        if not rule_id:
            rule_id = self._create_origin_rule(zone_id, ruleset_id, master_domain, slave_domains, public_port)
        else:
            rule_id = self._update_origin_rule(zone_id, ruleset_id, rule_id, master_domain, slave_domains, public_port)
        return rule_id

    def del_origin_rule(self, master_domain):
        zone_id = self._find_zone_id(master_domain)
        ruleset_id = self._get_origin_ruleset(zone_id)
        rule_id = self._find_origin_rule(zone_id, ruleset_id, master_domain)
        if rule_id:
            rule_id = self._delete_origin_rule(zone_id, ruleset_id, rule_id)
        return rule_id

    def _url_req(self, url, data=None, method=None, retry=5):
        data_bin = None
        if data is not None:
            data_bin = json.dumps(data).encode()
        req = urllib.request.Request(url, data=data_bin, method=method)
        for i in range(retry):
            try:
                with self.opener.open(req, timeout=10) as res:
                    ret = json.load(res)
                break
            except urllib.error.HTTPError as e:
                time.sleep(5)
                ret = json.load(e)
        if "errors" not in ret:
            raise RuntimeError(ret)
        if not ret.get("success"):
            raise RuntimeError(ret["errors"])
        return ret

    def _find_zone_id(self, name):
        name = name.lower()
        data = self._url_req(
            f"https://api.cloudflare.com/client/v4/zones"
        )
        for zone_data in data["result"]:
            zone_name = zone_data["name"]
            if name == zone_name or name.endswith("." + zone_name):
                zone_id = zone_data["id"]
                return zone_id
        return None

    def _find_a_record(self, zone_id, name):
        name = name.lower()
        data = self._url_req(
            f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"
        )
        for rec_data in data["result"]:
            # if rec_data["type"] == type and rec_data["name"] == name:
            if rec_data["name"] == name:
                rec_id = rec_data["id"]
                return rec_id
        return None

    def _create_a_record(self, zone_id, name, ipaddr, proxied=False, ttl=120, type="A"):
        name = name.lower()
        data = self._url_req(
            f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records",
            data={
                "content":  ipaddr,
                "name":     name,
                "proxied":  proxied,
                "type":     type,
                "ttl":      ttl
            },
            method="POST"
        )
        return data["result"]["id"]

    def _update_a_record(self, zone_id, rec_id, name, ipaddr, proxied=False, ttl=120, type="A"):
        name = name.lower()
        data = self._url_req(
            f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{rec_id}",
            data={
                "content":  ipaddr,
                "name":     name,
                "proxied":  proxied,
                "type":     type,
                "ttl":      ttl
            },
            method="PUT"
        )
        return data["result"]["id"]

    def _get_origin_ruleset(self, zone_id):
        data = self._url_req(
            f"https://api.cloudflare.com/client/v4/zones/{zone_id}/rulesets"
        )
        for ruleset_data in data["result"]:
            if ruleset_data["phase"] == "http_request_origin":
                ruleset_id = ruleset_data["id"]
                return ruleset_id
        return None

    def _get_origin_description(self, master_domain):
        return f"Natter: {master_domain}"

    def _find_origin_rule(self, zone_id, ruleset_id, master_domain):
        data = self._url_req(
            f"https://api.cloudflare.com/client/v4/zones/{zone_id}/rulesets/{ruleset_id}"
        )
        if "rules" not in data["result"]:
            return None
        for rule_data in data["result"]["rules"]:
            if rule_data["description"] == self._get_origin_description(master_domain):
                rule_id = rule_data["id"]
                return rule_id
        return None

    def _create_origin_rule(self, zone_id, ruleset_id, master_domain, slave_domains, public_port):
        domains = [master_domain]
        domains.extend(slave_domains)
        data = self._url_req(
            f"https://api.cloudflare.com/client/v4/zones/{zone_id}/rulesets/{ruleset_id}/rules",
            data={
                "action": "route",
                "action_parameters": {
                    "origin": {
                        "port": int(public_port)
                    }
                },
                "description": self._get_origin_description(master_domain),
                "enabled": True,
                "expression": '(' + ' or '.join([f'http.host eq "{x}"' for x in domains]) + ')'
            },
            method="POST"
        )
        for rule_data in data["result"]["rules"]:
            if rule_data["description"] == self._get_origin_description(master_domain):
                rule_id = rule_data["id"]
                return rule_id
        raise RuntimeError("Failed to create origin rule")

    def _update_origin_rule(self, zone_id, ruleset_id, rule_id, master_domain, slave_domains, public_port):
        domains = [master_domain]
        domains.extend(slave_domains)
        data = self._url_req(
            f"https://api.cloudflare.com/client/v4/zones/{zone_id}/rulesets/{ruleset_id}/rules/{rule_id}",
            data={
                "action": "route",
                "action_parameters": {
                    "origin": {
                        "port": int(public_port)
                    }
                },
                "description": self._get_origin_description(master_domain),
                "enabled": True,
                "expression": '(' + ' or '.join([f'http.host eq "{x}"' for x in domains]) + ')'
            },
            method="PATCH"
        )
        for rule_data in data["result"]["rules"]:
            if rule_data["description"] == self._get_origin_description(master_domain):
                rule_id = rule_data["id"]
                return rule_id
        raise RuntimeError("Failed to update origin rule")

    def _delete_origin_rule(self, zone_id, ruleset_id, rule_id):
        data = self._url_req(
            f"https://api.cloudflare.com/client/v4/zones/{zone_id}/rulesets/{ruleset_id}/rules/{rule_id}",
            method="DELETE"
        )
        return data["result"]["id"]

def main():
    natter_post = NatterPost()
    if len(sys.argv) == 6:
        update_derp_only = True
        if sys.argv[1] == "tcp":
            update_derp_only = natter_post.update_ipv6_address(force_update=True)
        natter_post.update_ipv4_address(update_derp_only)
    else:
        # 定期同步一次证书
        schedule.every(1).minutes.do(natter_post.sync_certificates, acme_json_path=natter_post.acme_json_file, derp_dir=natter_post.derp_dir, domain=natter_post.derp_domain)
        schedule.every(1).minutes.do(natter_post.update_ipv6_address)
        natter_post.run_schedule()

if __name__ == "__main__":
    main()
