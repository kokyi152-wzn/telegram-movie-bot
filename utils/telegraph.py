import aiohttp
from config import TELEGRAPH_TOKEN

API_URL = "https://api.telegra.ph"


async def create_page(title, content, author_name="Movie Bot", author_url=""):
    if not TELEGRAPH_TOKEN:
        return None

    async with aiohttp.ClientSession() as session:
        data = aiohttp.FormData()
        data.add_field("access_token", TELEGRAPH_TOKEN)
        data.add_field("title", title)
        data.add_field("author_name", author_name)
        if author_url:
            data.add_field("author_url", author_url)
        data.add_field("content", content)
        data.add_field("return_content", "true")

        async with session.post(f"{API_URL}/createPage", data=data) as resp:
            result = await resp.json()
            if result.get("ok"):
                return result["result"]["url"]
            return None


async def edit_page(path, title, content, author_name="Movie Bot"):
    if not TELEGRAPH_TOKEN:
        return None

    async with aiohttp.ClientSession() as session:
        data = aiohttp.FormData()
        data.add_field("access_token", TELEGRAPH_TOKEN)
        data.add_field("path", path)
        data.add_field("title", title)
        data.add_field("author_name", author_name)
        data.add_field("content", content)

        async with session.post(f"{API_URL}/editPage", data=data) as resp:
            result = await resp.json()
            if result.get("ok"):
                return f"https://telegra.ph/{path}"
            return None


async def create_account(short_name="MovieBot", author_name="Movie Bot"):
    async with aiohttp.ClientSession() as session:
        data = aiohttp.FormData()
        data.add_field("short_name", short_name)
        data.add_field("author_name", author_name)

        async with session.post(f"{API_URL}/createAccount", data=data) as resp:
            result = await resp.json()
            if result.get("ok"):
                return result["result"]["access_token"]
            return None


def text_to_content(text):
    paragraphs = text.split("\n\n")
    content = []
    for p in paragraphs:
        p = p.strip()
        if p:
            content.append({"tag": "p", "children": [p]})
    if not content:
        content = [{"tag": "p", "children": [text]}]
    return content
