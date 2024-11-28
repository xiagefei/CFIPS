import dns.resolver
import requests


def get_a_records(domain):
    a_records = []
    try:
        answers = dns.resolver.resolve(domain, 'A')
        for rdata in answers:
            a_records.append(rdata.address)
    except dns.resolver.NoAnswer:
        print(f"No A records found for {domain}")
    except dns.resolver.NXDOMAIN:
        print(f"The domain {domain} does not exist.")
    except Exception as e:
        print(f"An error occurred: {e}")

    return a_records


if __name__ == "__main__":
    # 从指定的URL获取域名列表
    url = "https://raw.githubusercontent.com/leung7963/CFIPS/refs/heads/main/domain.txt"
    response = requests.get(url)
    if response.status_code == 200:
        domains = response.text.splitlines()
    else:
        print(f"无法从指定URL获取域名列表，状态码: {response.status_code}")
        exit(1)

    with open("domain_ips.txt", "w") as output_file:
        for domain in domains:
            domain = domain.strip()
            a_records = get_a_records(domain)

            if a_records:
                for record in a_records:
                    output_file.write(record + "\n")
                output_file.write("\n")