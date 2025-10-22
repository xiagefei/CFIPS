import requests
import traceback
import time
import os
import json
import random  # 新增随机模块

# API 密钥
CF_API_TOKEN = os.environ["CF_API_TOKEN"]
CF_ZONE_ID = os.environ["CF_ZONE_ID"]
CF_DNS_NAME = os.environ["CF_DNS_NAME"]

# pushplus_token
PUSHPLUS_TOKEN = os.environ["PUSHPLUS_TOKEN"]

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

headers = {
    'Authorization': f'Bearer {CF_API_TOKEN}',
    'Content-Type': 'application/json'
}

# 从URL获取IP地址列表并随机选择5个
def get_cf_speed_test_ip():
    url = "https://raw.githubusercontent.com/leung7963/CFIPS/main/ip.js"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # 检查HTTP错误
        ip_list = response.text.strip().split()  # 获取所有IP列表
        
        # 随机选择5个IP（如果IP数量不足5个则选择全部）
        return random.sample(ip_list, min(1, len(ip_list))) if ip_list else None
    except Exception as e:
        traceback.print_exc()
        print(f"从URL获取IP失败: {e}")
    return None


# 获取 DNS 记录
def get_dns_records(name):
    def_info = []
    url = f'https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records'
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        records = response.json()['result']
        for record in records:
            if record['name'] == name:
                def_info.append(record['id'])
        return def_info
    else:
        print('Error fetching DNS records:', response.text)


# 更新 DNS 记录
def update_dns_record(record_id, name, cf_ip):
    url = f'https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records/{record_id}'
    data = {
        'type': 'A',
        'name': name,
        'content': cf_ip
    }

    response = requests.put(url, headers=headers, json=data)

    if response.status_code == 200:
        print(f"cf_dns_change success: ---- Time: " + str(
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())) + " ---- ip：" + str(cf_ip))
        return "ip:" + str(cf_ip) + "解析" + str(name) + "成功"
    else:
        traceback.print_exc()
        print(f"cf_dns_change ERROR: ---- Time: " + str(
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())) + " ---- MESSAGE: " + str(name))
        return "ip:" + str(cf_ip) + "解析" + str(name) + "失败"


# 消息推送
def push_plus(content):
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
    data = {
        "chat_id": CHAT_ID,
        "title": "IP优选DNSCF推送",
        "text": content,
        "template": "markdown",
        "channel": "wechat"
    }
    body = json.dumps(data).encode(encoding='utf-8')
    headers = {'Content-Type': 'application/json'}
    requests.post(url, data=body, headers=headers)


# 主函数
def main():
    # 获取随机优选IP（最多5个）
    ip_addresses = get_cf_speed_test_ip()
    if not ip_addresses:
        print("未获取到有效IP地址")
        return
        
    dns_records = get_dns_records(CF_DNS_NAME)
    if not dns_records:
        print("未找到匹配的DNS记录")
        return
        
    push_plus_content = []
    # 遍历 IP 地址列表
    for index, ip_address in enumerate(ip_addresses[:len(dns_records)]):
        # 执行 DNS 变更
        dns = update_dns_record(dns_records[index], CF_DNS_NAME, ip_address)
        push_plus_content.append(dns)

    # 添加随机选择的IP信息
    push_plus_content.insert(0, f"本次随机选择的IP: {', '.join(ip_addresses)}")
    push_plus('\n'.join(push_plus_content))


if __name__ == '__main__':
    main()