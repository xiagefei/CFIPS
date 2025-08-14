import re
import os
import requests

# 目标 URL 列表
urls = [
    'https://raw.githubusercontent.com/leung7963/CFIPS/main/domain_ips.js'
]

# 正则表达式用于匹配 IP 地址
ip_pattern = r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'

# 检查 ip.js 文件是否存在，如果存在则删除它
if os.path.exists('ip.js'):
    os.remove('ip.js')

all_ips = []
for url in urls:
    try:
        # 使用 requests 获取内容
        response = requests.get(url)
        response.raise_for_status()  # 检查请求是否成功
        
        # 使用正则表达式查找 IP 地址
        ip_matches = re.findall(ip_pattern, response.text)
        all_ips.extend(ip_matches)
    except Exception as e:
        print(f"处理 {url} 时出错: {e}")

# 过滤出以172或162开头的IP并去重
filtered_ips = set()
for ip in all_ips:
    # 检查IP是否以172或162开头
    if ip.startswith('172.') or ip.startswith('162.'):
        filtered_ips.add(ip)

# 将结果写入文件
with open('ip.js', 'w') as file:
    for ip in filtered_ips:
        file.write(ip + '\n')

print(f'已保存 {len(filtered_ips)} 个172和162开头的IP地址到 ip.js 文件。')