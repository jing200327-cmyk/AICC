from __future__ import annotations

from pathlib import Path

from .models import StoreScript


class StoreScriptRegistry:
    def __init__(self, stores: list[StoreScript]):
        self._stores = {store.store_code: store for store in stores}

    @classmethod
    def default(cls) -> "StoreScriptRegistry":
        root = Path(__file__).resolve().parents[2]
        scripts = root / "线索变量脚本"
        return cls(
            [
                StoreScript("hefei_haikangda", "合肥海康达店", "合肥", "马自达", ["合肥海康达", "海康达"], str(scripts / "合肥海康达.py"), "合肥海康达"),
                StoreScript("hefei_mazda", "合肥建银马自达店", "合肥", "马自达", ["合肥马自达", "合肥建银马自达", "建银马自达"], str(scripts / "合肥马自达.py"), "合肥马自达"),
                StoreScript("tianxiang_lincoln", "天翔林肯店", "", "林肯", ["天翔林肯", "天翔"], str(scripts / "天翔林肯.py"), "天翔林肯"),
                StoreScript("lincoln_meicheng", "林肯美诚店", "", "林肯", ["林肯美诚", "美诚林肯", "美诚"], str(scripts / "林肯美诚.py"), "林肯美诚"),
                StoreScript("wuhan_yinma", "武汉银马店", "武汉", "马自达", ["武汉银马", "银马"], str(scripts / "武汉银马.py"), "武汉银马"),
                StoreScript("xiangyang_lincoln", "襄阳林肯店", "襄阳", "林肯", ["襄阳林肯", "襄阳"], str(scripts / "襄阳林肯.py"), "襄阳林肯"),
                StoreScript("junma_zhongcheng", "骏马众诚店", "武汉", "马自达", ["骏马众诚", "骏马众城", "武汉骏马", "骏马"], str(scripts / "骏马众诚.py"), "骏马众诚"),
                StoreScript("junma_last_month", "骏马众城-上月保养", "武汉", "马自达", ["骏马众城-上月保养", "上月保养"], str(scripts / "骏马众城-上月保养.py"), "骏马众城-上月保养"),
            ]
        )

    def list_stores(self) -> list[StoreScript]:
        return list(self._stores.values())

    def upsert(self, store: StoreScript) -> None:
        self._stores[store.store_code] = store

    def get(self, store_code: str) -> StoreScript:
        return self._stores[store_code]

    def has(self, store_code: str) -> bool:
        return store_code in self._stores
