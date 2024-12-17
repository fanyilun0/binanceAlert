import requests
import time
import aiohttp
import asyncio
import random
from datetime import datetime
from bs4 import BeautifulSoup
import json
import re

from config import COOKIE, WEBHOOK_URL, PROXY_URL, USE_PROXY, ALWAYS_NOTIFY, API_URL, MONITOR_INTERVAL

# HTML URL
api_url = API_URL

# 监控周期，单位：秒
monitor_interval = MONITOR_INTERVAL  # 每隔 60 秒查询一次

# 记录已经处理过的文章ID，避免重复提醒
processed_article_ids = set()

# 添加一个新的变量来存储上次的文章ID集合
last_article_ids = set()

async def send_message_async(message_content):
    """发送消息到企业微信机器人"""
    headers = {'Content-Type': 'application/json'}
    
    payload = {
        "msgtype": "text",
        "text": {
            "content": message_content
        }
    }
    
    proxy = PROXY_URL if USE_PROXY else None
    async with aiohttp.ClientSession() as session:
        async with session.post(WEBHOOK_URL, json=payload, headers=headers, proxy=proxy) as response:
            # print response
            # print(response)

            if response.status == 200:
                log_with_time("Message sent successfully!")
            else:
                log_with_time(f"Failed to send message: {response.status}")

# 打印时加上时间戳
def log_with_time(message):
    """打印带时间戳的消息"""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{current_time}] {message}")

def get_random_headers():   
    # 添加User-Agent池
    USER_AGENTS = [
        # Chrome
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        # Firefox
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:120.0) Gecko/20100101 Firefox/120.0",
        # Safari
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        # Edge
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
        # Mobile
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1.2 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
    ]
    """生成随机的请求头"""
    return {
        'authority': 'www.binance.com',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-encoding': 'gzip, deflate, br, zstd',
        'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7',
        'cache-control': 'max-age=0',
        'User-Agent': random.choice(USER_AGENTS),
        'cookie': COOKIE,
        'referer': 'https://www.binance.com/en/support/announcement/new-cryptocurrency-listing?c=48&navId=48&hl=en',
        'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1'
    }

def get_emoji_for_type(title):
    """根据公告标题返回相应的 emoji"""
    if "Introducing" in title or "上线" in title:
        return "🚀"  # 新币种上线
    elif "Launchpool" in title:
        return "🌱"  # LaunchPool
    elif "Futures" in title:
        return "📈"  # 合约
    elif "Options" in title:
        return "📊"  # 期货
    elif "Margin" in title:
        return "💹"  # Margin
    else:
        return "ℹ️"  # 其他

def build_listing_message(title, release_date, link):
    """构建新币种上线公告的推送消息"""
    emoji = get_emoji_for_type(title)  # 获取对应的 emoji
    return (
        f"{emoji} 新币种上线公告 📢\n"
        f"标题: {title}\n"
        f"时间: {release_date}\n"
        f"链接: {link if link else '无链接'}"
    )


def parse_listing_data(html_content):
    """从HTML内容中解析出新币上线信息"""
    try:
        # 查找包含目标数据的script标签
        pattern = r'<script id="__APP_DATA" type="application/json".*?>(.*?)</script>'
        script_content = re.search(pattern, html_content, re.DOTALL)

        # Debug
        # log_with_time(f"script_content: {script_content}")

        if not script_content:
            log_with_time("No APP_DATA script found")
            return None
            
        # 解析JSON数据
        json_data = json.loads(script_content.group(1))
        
        # 直接查找包含 catalogDetail 的路由
        route_data = None
        for route_content in json_data['appState']['loader']['dataByRouteId'].values():
            if 'catalogDetail' in route_content:
                route_data = route_content
                break
                
        if not route_data or 'catalogDetail' not in route_data:
            log_with_time("No route with catalogDetail found")
            return None
            
        catalog_detail = route_data['catalogDetail']

        log_with_time(f"catalog_detail: {catalog_detail}")

        if catalog_detail['catalogName'] != 'New Cryptocurrency Listing':
            log_with_time(f"Unexpected catalog name: {catalog_detail['catalogName']}")
            return None
            
        articles = catalog_detail['articles']
        log_with_time(f"Found {len(articles)} articles")
        
        formatted_articles = []
        for article in articles:
            formatted_article = {
                'id': article['id'],
                'code': article['code'],
                'title': article['title'],
                'release_date': datetime.fromtimestamp(article['releaseDate']/1000).strftime('%Y-%m-%d %H:%M:%S'),
                'link': build_article_link(article['title'], article['code'])
            }
            formatted_articles.append(formatted_article)
            
        return formatted_articles

    except json.JSONDecodeError as e:
        log_with_time(f"JSON parsing error: {e}")
    except Exception as e:
        log_with_time(f"Error parsing listing data: {e}")
        import traceback
        log_with_time(f"Detailed error: {traceback.format_exc()}")
    return None

def save_and_parse_html_content():
    """保存HTML内容并解析数据"""
    try:
        headers = get_random_headers()
        
        log_with_time("Starting request...")
        # log_with_time(f"Using Proxy: {PROXY_URL}")

        response = requests.get(api_url, headers=headers, timeout=10, 
                              proxies={'http': PROXY_URL, 'https': PROXY_URL} if USE_PROXY else None)
        log_with_time(f"Response status: {response.status_code}")
        
        html = response.text
        log_with_time(f"Received content length: {len(html)}")
        
        # 保存原始HTML
        with open('binance_listing.html', 'w', encoding='utf-8') as f:
            f.write(html)
        log_with_time("Raw HTML saved to binance_listing.html")
        
        # 解析数据
        articles = parse_listing_data(html)
        if articles:
            # 保存解析后的数据
            with open('binance_listing_data.json', 'w', encoding='utf-8') as f:
                json.dump(articles, f, ensure_ascii=False, indent=2)
            log_with_time("Parsed data saved to binance_listing_data.json")
            
            # 打印最新的5条公告
            log_with_time("\nLatest 5 announcements:")
            for article in articles[:5]:
                log_with_time(f"Title: {article['title']}")
                log_with_time(f"Release Date: {article['release_date']}")
                log_with_time("-" * 50)
        
        return articles
        
    except requests.RequestException as e:
        log_with_time(f"Request error: {e}")
    except Exception as e:
        log_with_time(f"Error in save_and_parse_html_content: {e}")
    return None

def build_article_link(title, code):
    """构建文章链接"""
    base_url = "https://www.binance.com/en/support/announcement/"
    # 将标题中的空格替换为 "-"，并将其转换为小写
    formatted_title = title.replace(" ", "-").lower()
    return f"{base_url}{formatted_title}-{code}"

# 修改 monitor 函数为异步函数
async def monitor():
    """启动监控程序"""
    global last_article_ids
    
    log_with_time("Starting monitor...")
    
    # 首次运行，获取当前文章列表
    initial_articles = save_and_parse_html_content()

    if initial_articles:
        last_article_ids = {article['id'] for article in initial_articles}
        log_with_time(f"Initialized with {len(last_article_ids)} articles")
        
        # 如果设置了ALWAYS_NOTIFY，则发送初始文章通知
        if ALWAYS_NOTIFY:
            for article in initial_articles[:5]:  # 只发送最新的5条
                filtered_title = article['title'].replace('Binance', '')
                message = (
                    f"📢 Initial Listing Alert 📢\n"
                    f"Title: {filtered_title}\n"
                    f"Time: {article['release_date']}\n"
                    f"Link: {article['link']}"
                )
                await send_message_async(message)

    while True:
        try:
            log_with_time("Checking for new articles...")
            articles = save_and_parse_html_content()
            
            if not articles:
                log_with_time("No articles found in this check")
                await asyncio.sleep(monitor_interval)
                continue
                
            # 获取当前文章ID集合
            current_article_ids = {article['id'] for article in articles}
            
            # 找出新增的文章ID
            new_article_ids = current_article_ids - last_article_ids
            
            if new_article_ids:
                log_with_time(f"Found {len(new_article_ids)} new articles")
                # 获取新文章的详细信息并发送通知
                for article in articles:
                    if article['id'] in new_article_ids:
                        link = article.get('link', '无链接')
                        message = build_listing_message(article['title'], article['release_date'], link)
                        log_with_time(f"Sending notification for article {article['id']}")
                        await send_message_async(message)
            else:
                log_with_time("No new articles found")
            
            # 更新上次的文章ID集合
            last_article_ids = current_article_ids
            
        except Exception as e:
            log_with_time(f"Error in monitor loop: {e}")
            # 发送错误通知
            await send_message_async(f"❌ Monitor Error: {str(e)}")
        
        log_with_time(f"Waiting for {monitor_interval} seconds before next check...")
        await asyncio.sleep(monitor_interval)


# 修改 main 部分
if __name__ == "__main__":
    # 正常监控模式
    asyncio.run(monitor())
