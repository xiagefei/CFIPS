import requests
import ipaddress
import random
import traceback
import time
import os
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

# 环境变量读取
CF_API_TOKEN = os.environ.get("CF_API_TOKEN")
CF_ZONE_ID = os.environ.get("CF_ZONE_ID")
CF_DNS_NAME = os.environ.get("CF_DNS_NAME")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
TEST_URL_TEMPLATE = os.environ.get("TEST_URL_TEMPLATE", "http://{ip}/")
EXPECTED_STATUS_CODE = int(os.environ.get("EXPECTED_STATUS_CODE", "403"))
MAX_RETRY_ATTEMPTS = int(os.environ.get("MAX_RETRY_ATTEMPTS", "5"))
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "5"))

def get_cloudflare_ips():
    """从Cloudflare获取IPv4地址范围"""
    url = "https://www.cloudflare.com/ips-v4/"
    
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

def test_ip_status(ip_address, test_url_template, expected_status_code=403):
    """测试IP地址是否返回指定状态码"""
    try:
        # 构建测试URL
        test_url = test_url_template.format(ip=ip_address)
        
        # 发送HTTP请求
        response = requests.get(
            test_url, 
            timeout=REQUEST_TIMEOUT,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            },
            allow_redirects=False  # 不跟随重定向
        )
        
        status_code = response.status_code
        print(f"测试 IP {ip_address}: 状态码 {status_code}, URL: {test_url}")
        
        # 检查是否为期望的状态码
        return status_code == expected_status_code, status_code, response.reason
        
    except requests.exceptions.Timeout:
        print(f"测试 IP {ip_address}: 请求超时")
        return False, 0, "Timeout"
    except requests.exceptions.ConnectionError:
        print(f"测试 IP {ip_address}: 连接错误")
        return False, 0, "Connection Error"
    except Exception as e:
        print(f"测试 IP {ip_address} 时发生异常: {e}")
        return False, 0, str(e)

def generate_and_test_ips(num_ips=5, max_retries_per_ip=3):
    """生成并测试IP地址，确保返回指定状态码"""
    print("正在获取Cloudflare IPv4地址范围...")
    cidrs = get_cloudflare_ips()
    
    if not cidrs:
        print("无法获取地址范围")
        return []
    
    print(f"获取到 {len(cidrs)} 个CIDR范围")
    print(f"测试配置: 期望状态码={EXPECTED_STATUS_CODE}, URL模板={TEST_URL_TEMPLATE}")
    
    # 存储符合条件的IP地址
    qualified_ips = []
    # 存储所有尝试过的IP及其结果
    attempted_ips = {}
    # 记录总尝试次数
    total_attempts = 0
    max_total_attempts = num_ips * 10  # 防止无限循环
    
    while len(qualified_ips) < num_ips and total_attempts < max_total_attempts:
        # 随机选择一个CIDR范围
        random_cidr = random.choice(cidrs)
        
        # 从该范围生成随机IP
        random_ip = generate_random_ip_from_cidr(random_cidr)
        
        if not random_ip:
            total_attempts += 1
            continue
        
        # 检查是否已经尝试过这个IP
        if random_ip in attempted_ips:
            total_attempts += 1
            continue
        
        # 测试IP
        is_qualified, status_code, reason = test_ip_status(
            random_ip, 
            TEST_URL_TEMPLATE, 
            EXPECTED_STATUS_CODE
        )
        
        # 记录尝试结果
        attempted_ips[random_ip] = {
            'qualified': is_qualified,
            'status_code': status_code,
            'reason': reason,
            'cidr': random_cidr
        }
        total_attempts += 1
        
        if is_qualified:
            qualified_ips.append(random_ip)
            print(f"✓ 找到合格IP {len(qualified_ips)}/{num_ips}: {random_ip} (来自范围: {random_cidr})")
        else:
            print(f"✗ IP不合格: {random_ip} (状态码: {status_code}, 原因: {reason})")
    
    # 如果循环结束但未找到足够数量的合格IP
    if len(qualified_ips) < num_ips:
        print(f"警告: 只找到 {len(qualified_ips)} 个合格IP，目标为 {num_ips} 个")
        print(f"总尝试次数: {total_attempts}, 尝试过的IP数量: {len(attempted_ips)}")
        
        # 打印一些统计信息
        status_counts = {}
        for ip_info in attempted_ips.values():
            status = ip_info['status_code']
            status_counts[status] = status_counts.get(status, 0) + 1
        
        print("状态码统计:")
        for status, count in status_counts.items():
            print(f"  状态码 {status}: {count} 个IP")
    
    return qualified_ips

def generate_random_ips_with_retry(num_ips=5):
    """生成指定数量的随机IP地址，如果不符合要求则重试"""
    return generate_and_test_ips(num_ips, MAX_RETRY_ATTEMPTS)

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
    print("=" * 60)
    print("Cloudflare IP优选工具 - 带状态码测试的随机IP生成")
    print("=" * 60)
    print(f"测试配置:")
    print(f"  - 测试URL模板: {TEST_URL_TEMPLATE}")
    print(f"  - 期望状态码: {EXPECTED_STATUS_CODE}")
    print(f"  - 最大重试次数: {MAX_RETRY_ATTEMPTS}")
    print(f"  - 请求超时: {REQUEST_TIMEOUT}秒")
    
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
    
    # 生成并测试随机IP
    num_ips = max(5, len(dns_records)) if dns_records else 5
    print(f"\n正在生成并测试 {num_ips} 个随机IP地址...")
    print(f"要求IP地址返回状态码: {EXPECTED_STATUS_CODE}")
    
    generated_ips = generate_random_ips_with_retry(num_ips=num_ips)
    
    if not generated_ips:
        print("错误: 无法生成任何符合条件的IP地址")
        # 尝试生成普通IP（不测试）作为备选
        print("尝试生成普通IP地址...")
        generated_ips = generate_and_test_ips(num_ips, 0)  # 0重试，只生成不测试
        if not generated_ips:
            return
    
    print(f"\n成功生成 {len(generated_ips)} 个符合条件的IP地址:")
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
        push_content.insert(2, f"测试配置: 期望状态码={EXPECTED_STATUS_CODE}")
        push_content.insert(3, f"生成的IP地址: {', '.join(generated_ips)}")
        
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
    
    print("=" * 60)
    print("程序执行完毕")

if __name__ == "__main__":
    main()