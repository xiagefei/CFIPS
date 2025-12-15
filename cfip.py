import requests
import ipaddress
import random
import traceback
import time
import os
import json

# 环境变量读取
CF_API_TOKEN = os.environ.get("CF_API_TOKEN")
CF_ZONE_ID = os.environ.get("CF_ZONE_ID")
CF_DNS_NAME = os.environ.get("CF_DNS_NAME")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")

def get_cloudflare_ips():
    """从Cloudflare获取IPv4地址范围"""
    url = "https://raw.githubusercontent.com/leung7963/CFIPS/main/cfasn"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        # 按行分割，去除空白行
        cidrs = [line.strip() for line in response.text.split('\n') if line.strip()]
        return cidrs
    except requests.RequestException as e:
        print(f"获取IP地址范围失败: {e}")
        return []

def generate_random_ip_from_cidr(cidr):
    """从CIDR范围内生成随机IP地址"""
    try:
        network = ipaddress.ip_network(cidr, strict=False)
        
        # 计算网络地址和广播地址
        network_address = int(network.network_address)
        broadcast_address = int(network.broadcast_address)
        
        # 生成网络地址和广播地址之间的随机IP
        if network.prefixlen <= 30:  # 对于大多数网络，排除网络和广播地址
            start_ip = network_address + 1
            end_ip = broadcast_address - 1
        else:  # 对于/31和/32网络，特殊处理
            start_ip = network_address
            end_ip = broadcast_address
        
        # 生成随机IP
        random_ip_int = random.randint(start_ip, end_ip)
        random_ip = ipaddress.IPv4Address(random_ip_int)
        
        return str(random_ip)
    except Exception as e:
        print(f"从CIDR {cidr} 生成IP失败: {e}")
        return None

def generate_random_ips(num_ips=5):
    """从Cloudflare IP范围生成指定数量的随机IP地址"""
    print("正在获取Cloudflare IPv4地址范围...")
    cidrs = get_cloudflare_ips()
    
    if not cidrs:
        print("无法获取地址范围")
        return []
    
    print(f"获取到 {len(cidrs)} 个CIDR范围")
    
    # 生成指定数量的随机IP
    ip_list = []
    attempts = 0
    max_attempts = num_ips * 3  # 最大尝试次数
    
    while len(ip_list) < num_ips and attempts < max_attempts:
        # 随机选择一个CIDR范围
        random_cidr = random.choice(cidrs)
        
        # 从该范围生成随机IP
        random_ip = generate_random_ip_from_cidr(random_cidr)
        
        if random_ip and random_ip not in ip_list:
            ip_list.append(random_ip)
            print(f"{len(ip_list)}. IP: {random_ip} (来自范围: {random_cidr})")
        
        attempts += 1
    
    return ip_list

def get_dns_records(name):
    """获取 DNS 记录"""
    if not CF_API_TOKEN or not CF_ZONE_ID:
        print("缺少必要的环境变量")
        return []
        
    headers = {
        'Authorization': f'Bearer {CF_API_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    def_info = []
    url = f'https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records'
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            records = response.json()['result']
            for record in records:
                if record['name'] == name:
                    def_info.append(record['id'])
            return def_info
        else:
            print('获取DNS记录失败:', response.text)
    except Exception as e:
        print(f"获取DNS记录失败: {e}")
    return []

def update_dns_record(record_id, name, cf_ip):
    """更新 DNS 记录"""
    if not CF_API_TOKEN or not CF_ZONE_ID:
        print("缺少必要的环境变量")
        return "更新失败: 缺少API配置"
        
    headers = {
        'Authorization': f'Bearer {CF_API_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    url = f'https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records/{record_id}'
    data = {
        'type': 'A',
        'name': name,
        'content': cf_ip,
        'ttl': 86400
    }

    try:
        response = requests.put(url, headers=headers, json=data)

        if response.status_code == 200:
            print(f"DNS更新成功: ---- 时间: " + str(
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())) + " ---- IP：" + str(cf_ip))
            return "IP:" + str(cf_ip) + " 解析 " + str(name) + " 成功"
        else:
            print(f"DNS更新失败: ---- 时间: " + str(
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())) + " ---- 错误信息: " + str(response.text))
            return "IP:" + str(cf_ip) + " 解析 " + str(name) + " 失败"
    except Exception as e:
        traceback.print_exc()
        print(f"DNS更新异常: {e}")
        return "IP:" + str(cf_ip) + " 解析 " + str(name) + " 异常"

def push_notification(content):
    """Telegram消息推送"""
    if not BOT_TOKEN or not CHAT_ID:
        print("未配置BOT_TOKEN或CHAT_ID，跳过消息推送")
        return
    
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
    data = {
        "chat_id": CHAT_ID,
        "title": "Cloudflare IP优选及DNS更新",
        "text": content,
        "parse_mode": "Markdown"
    }
    
    try:
        body = json.dumps(data).encode(encoding='utf-8')
        headers = {'Content-Type': 'application/json'}
        response = requests.post(url, data=body, headers=headers)
        if response.status_code == 200:
            print("消息推送成功")
        else:
            print(f"消息推送失败: {response.text}")
    except Exception as e:
        print(f"消息推送异常: {e}")

def save_ips_to_file(ip_list, filename='cfip.txt'):
    """将IP地址保存到文件"""
    try:
        with open(filename, 'w', encoding='utf-8') as file:
            for ip in ip_list:
                file.write(ip + '\n')
        print(f"IP地址已保存到 {filename} 文件中")
        return True
    except Exception as e:
        print(f"保存IP地址到文件失败: {e}")
        return False

def main():
    """主函数"""
    print("=" * 50)
    print("Cloudflare IP优选工具 - 从官方IP范围生成随机IP")
    print("=" * 50)
    
    # 获取DNS记录（如果配置了环境变量）
    dns_records = []
    if CF_API_TOKEN and CF_ZONE_ID and CF_DNS_NAME:
        print(f"\n正在获取DNS记录: {CF_DNS_NAME}")
        dns_records = get_dns_records(CF_DNS_NAME)
        if dns_records:
            print(f"找到 {len(dns_records)} 条DNS记录")
        else:
            print(f"未找到匹配 {CF_DNS_NAME} 的DNS记录")
    else:
        print("\n注意: 未配置完整的Cloudflare API环境变量")
        print("将只生成IP列表，不更新DNS记录")
    
    # 生成随机IP
    num_ips = max(5, len(dns_records)) if dns_records else 5
    print(f"\n正在生成 {num_ips} 个随机IP地址...")
    
    generated_ips = generate_random_ips(num_ips=num_ips)
    
    if not generated_ips:
        print("错误: 无法生成任何IP地址")
        return
    
    print(f"\n成功生成 {len(generated_ips)} 个IP地址:")
    for i, ip in enumerate(generated_ips, 1):
        print(f"{i}. {ip}")
    
    # 保存IP到文件
    save_ips_to_file(generated_ips)
    
    # 更新DNS记录（如果配置了环境变量且有DNS记录）
    if CF_API_TOKEN and CF_ZONE_ID and CF_DNS_NAME and dns_records:
        print("\n开始更新DNS记录...")
        push_content = []
        
        # 遍历IP地址和DNS记录
        for index, ip_address in enumerate(generated_ips[:len(dns_records)]):
            record_id = dns_records[index]
            result = update_dns_record(record_id, CF_DNS_NAME, ip_address)
            push_content.append(result)
        
        # 添加IP信息到推送内容
        push_content.insert(0, f"**Cloudflare IP优选结果**")
        push_content.insert(1, f"更新时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}")
        push_content.insert(2, f"生成的IP地址: {', '.join(generated_ips)}")
        
        # 发送推送通知
        push_notification('\n'.join(push_content))
        print("\nDNS记录更新完成")
    else:
        print("\n未更新DNS记录，原因:")
        if not CF_API_TOKEN:
            print("- 缺少 CF_API_TOKEN")
        if not CF_ZONE_ID:
            print("- 缺少 CF_ZONE_ID")
        if not CF_DNS_NAME:
            print("- 缺少 CF_DNS_NAME")
        if not dns_records:
            print(f"- 未找到 {CF_DNS_NAME} 的DNS记录")
        print("\nIP地址已保存到 cfip.txt 文件")
    
    print("=" * 50)
    print("程序执行完毕")

if __name__ == "__main__":
    main()