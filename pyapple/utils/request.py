from aiohttp import ClientSession
from typing import Optional, Any

from ..interface import HTTPException

SWSCAN_BASE = "https://swscan.apple.com/content/catalogs/others"
IPSW_BASE = "https://api.ipsw.me/v4"
CYDIA_BASE = " https://api.parcility.co/db"


class Base:
    def __init__(self) -> None:
        self.session: Optional[ClientSession] = None

    async def request(
        self,
        url: str,
        method: str,
        return_type: str,
        **kwargs: Any,
    ):
        if not self.session or self.session.closed:
            self.session = ClientSession()

        resp = await self.session.request(method, url, **kwargs)

        if resp.status == 200:
            return await getattr(resp, return_type)()

        else:
            raise HTTPException(resp.status, url)

    async def post(self, url: str, **kwargs: Any):
        if not self.session or self.session.closed:
            self.session = ClientSession()

        return await self.request(url, "POST", **kwargs)

    async def get(self, url: str, **kwargs: Any):
        if not self.session or self.session.closed:
            self.session = ClientSession()

        return await self.request(url, "GET", **kwargs)


class AsyncRequest(Base):
    async def ipsw(self, endpoint: str, **kwargs):
        url = IPSW_BASE + endpoint
        return await self.get(url, **kwargs)

    async def cydia(self, endpoint: str, **kwargs):
        url = CYDIA_BASE + endpoint
        data = await self.get(url, **kwargs)

        if data["status"] and data["code"] == 200:
            return data

        raise HTTPException(data["code"], url)

    async def swscan(self, index: str, headers=None, **kwargs):
        url = SWSCAN_BASE + index
        return await self.get(url, headers=headers, **kwargs)
