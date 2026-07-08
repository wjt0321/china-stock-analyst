from desktop.scrapling_adapters.eastmoney import EastmoneyScraper
from desktop.scrapling_adapters.sina import SinaScraper
from desktop.scrapling_adapters.ths import ThsScraper
from desktop.scrapling_adapters.tencent import TencentScraper


def test_all_adapters_have_required_interface():
    adapters = [EastmoneyScraper, SinaScraper, ThsScraper, TencentScraper]
    for cls in adapters:
        inst = cls()
        assert inst.name
        assert isinstance(inst.priority, int)
        assert hasattr(inst, "fetch_quote")
