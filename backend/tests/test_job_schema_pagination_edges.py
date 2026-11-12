"""调度任务 schema / 分页工具边缘。"""

from __future__ import annotations

import pytest

from app.core.base_schema import PageResultSchema




async def test_pagination_util() -> None:
    from app.common.request import PaginationService
    p = await PaginationService.paginate([1, 2, 3], None, None)
    assert p.page_no == 1 and p.page_size == 10 and p.has_next is False
    p2 = await PaginationService.paginate([1, 2, 3], 1, 2)
    assert p2.items == [1, 2] and p2.has_next is True
    with pytest.raises(Exception):
        await PaginationService.paginate([1], 0, 10)
    with pytest.raises(Exception):
        await PaginationService.paginate([1], 1, 0)
