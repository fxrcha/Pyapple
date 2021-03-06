import plistlib
import re
from contextlib import suppress
from typing import List, Optional

from ..interface import MacOSProduct, Package
from ..utils import AsyncRequest

OSINSTALL = {
    "User-Agent": "osinstallersetupplaind (unknown version) CFNetwork/720.5.7 Darwin/14.5.0 (x86_64)"
}
SWUPDATE = {
    "User-Agent": "Software%20Update (unknown version) CFNetwork/807.0.1 Darwin/16.0.0 (x86_64)"
}

CATLOG_SUF = {
    "publicbeta": "beta",  # Apple Beta Software Program
    "publicrelease": "",  # Public Release (most of users)
    "customerseed": "customerseed",
    "developerbeta": "seed",  # Developer Beta, which you can get from betaprofiles.com
}

MACOS_NAME = {
    "8": "mountainlion",
    "7": "lion",
    "6": "snowleopard",
    "5": "leopard",
}

MACOS_FULLNAME = {
    "tiger": "10.4",
    "leopard": "10.5",
    "snow leopard": "10.6",
    "lion": "10.7",
    "mountain lion": "10.8",
    "mavericks": "10.9",
    "yosemite": "10.10",
    "el capitan": "10.11",
    "sierra": "10.12",
    "high sierra": "10.13",
    "mojave": "10.14",
    "catalina": "10.15",
    "big sur": "10.16",
    "monterey": "10.17",
}


class SWSCAN:
    def __init__(self):
        self.HTTP = AsyncRequest()
        self.min_macos = 5
        self.max_macos = 16
        super().__init__()

    def build_url(self, catalog_id: str) -> str:
        catalog = catalog_id.lower()
        url = "/index-"

        url += "-".join(
            [
                MACOS_NAME[str(x)] if str(x) in MACOS_NAME else "10." + str(x)
                for x in reversed(range(self.min_macos, self.max_macos + 1))
            ]
        )

        url += ".merged-1.sucatalog"

        ver_s = (
            MACOS_NAME[str(self.max_macos)]
            if str(self.max_macos) in MACOS_NAME
            else "10." + str(self.max_macos)
        )

        if CATLOG_SUF[catalog]:
            url = url.replace(ver_s, ver_s + CATLOG_SUF[catalog] + "-" + ver_s)

        return url

    async def fetch_catalog(self, catalog_id="publicrelease"):
        raw_catalog = await self.HTTP.swscan(
            self.build_url(catalog_id), headers=OSINSTALL, return_type="text"
        )
        catalog_data = bytes(raw_catalog, "utf-8")
        self.root = plistlib.loads(catalog_data)

    async def valid_products(
        self, catalog_id="publicrelease", fetch_recovery: bool = False
    ):
        if not hasattr(self, "root"):
            await self.fetch_catalog(catalog_id)

        if not fetch_recovery:
            return [
                p
                for p in self.root.get("Products", {})
                if self.root.get("Products", {})
                .get(p, {})
                .get("ExtendedMetaInfo", {})
                .get("InstallAssistantPackageIdentifiers", {})
                .get("OSInstall", {})
                == "com.apple.mpkg.OSInstall"
                or self.root.get("Products", {})
                .get(p, {})
                .get("ExtendedMetaInfo", {})
                .get("InstallAssistantPackageIdentifiers", {})
                .get("SharedSupport", "")
                .startswith("com.apple.pkg.InstallAssistant")
            ]

        else:
            return [
                p
                for p in self.root.get("Products", {})
                if any(
                    x
                    for x in self.root.get("Products", {})
                    .get(p, {})
                    .get("Packages", [])
                    if x["URL"].endswith(
                        ("RecoveryHDUpdate.pkg", "RecoveryHDMetaDmg.pkg")
                    )
                )
            ]

    async def fetch_macos(
        self, catalog_id="publicrelease", fetch_recovery: bool = False
    ):
        macos_dict = []
        if not hasattr(self, "root"):
            await self.fetch_catalog(catalog_id)

        vaild_ids = await self.valid_products(catalog_id, fetch_recovery)

        for product_id in vaild_ids:
            metadata = await self.get_metadata(product_id)
            macos_dict.append(MacOSProduct(**metadata))

        await self.HTTP.session.close()
        return macos_dict

    async def search_macos(
        self,
        title: Optional[str],
        buildid: Optional[str],
        version: Optional[str],
        catalog_id="publicrelease",
        fetch_recovery: bool = False,
    ):
        macos_dict = []
        if not hasattr(self, "root"):
            await self.fetch_catalog(catalog_id)

        vaild_ids = await self.valid_products(catalog_id, fetch_recovery)

        for product_id in vaild_ids:
            metadata = await self.get_metadata(product_id)
            if (
                metadata["title"] == title
                or metadata["buildid"] == buildid
                or metadata["version"] == version
            ):
                macos_dict.append(MacOSProduct(**metadata))

        await self.HTTP.session.close()
        return macos_dict

    async def get_metadata(self, product_id: str, catalog_id="publicrelease"):
        if not hasattr(self, "root"):
            await self.fetch_catalog(catalog_id)

        try:
            resp = await self.HTTP.request(
                method="GET",
                url=self.root["Products"][product_id]["ServerMetadataURL"],
                return_type="text",
            )

            smd = plistlib.loads(bytes(resp, "utf-8"))
            name = smd["localization"]["English"]["title"]
            version = smd["CFBundleShortVersionString"]

            dist_file = await self.HTTP.request(
                method="GET",
                url=self.root["Products"][product_id]["Distributions"]["English"],
                return_type="text",
            )

            build_search = (
                "macOSProductBuildVersion"
                if "macOSProductBuildVersion" in dist_file
                else "BUILD"
            )

            with suppress(Exception):
                build = (
                    dist_file.split("<key>{}</key>".format(build_search))[1]
                    .split("<string>")[1]
                    .split("</string>")[0]
                )

        except:
            dist_file = await self.HTTP.request(
                url=self.root["Products"][product_id]["Distributions"]["English"],
                method="GET",
                return_type="text",
            )

            build_search = (
                "macOSProductBuildVersion"
                if "macOSProductBuildVersion" in dist_file
                else "BUILD"
            )

            vers_search = (
                "macOSProductVersion"
                if "macOSProductVersion" in dist_file
                else "VERSION"
            )

            with suppress(Exception):
                build = (
                    dist_file.split("<key>{}</key>".format(build_search))[1]
                    .split("<string>")[1]
                    .split("</string>")[0]
                )

            with suppress(Exception):
                version = (
                    dist_file.split("<key>{}</key>".format(vers_search))[1]
                    .split("<string>")[1]
                    .split("</string>")[0]
                )

            with suppress(Exception):
                name = re.search(r"<title>(.+?)</title>", dist_file).group(1)

        return {
            "product_id": product_id,
            "title": name,
            "version": version,
            "buildid": build,
            "postdate": self.root.get("Products", {})
            .get(product_id, {})
            .get("PostDate", ""),
            "packages": [
                Package(url=package["URL"], filesize=package["Size"])
                for package in self.root["Products"][product_id]["Packages"]
            ],
        }
