# -*- coding: utf-8 -*-
"""
分页结果 —— 对标 MyBatis-Plus IPage / Page
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Generic, List, Optional, TypeVar

T = TypeVar("T")


@dataclass
class Page(Generic[T]):
    """
    records: 当前页数据
    total:   总条数
    page:    当前页（从 1 开始）
    size:    每页条数
    """
    records: List[T] = field(default_factory=list)
    total: int = 0
    page: int = 1
    size: int = 10

    # 兼容别名（有人习惯 current / pages）
    @property
    def current(self) -> int:
        return self.page

    @property
    def pages(self) -> int:
        if self.size is None or self.size <= 0:
            return 0
        return (int(self.total) + int(self.size) - 1) // int(self.size)

    @property
    def has_next(self) -> bool:
        return self.page < self.pages

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    def to_dict(self) -> Dict[str, Any]:
        # records 里若是 BaseModel，尽量转 dict
        items: List[Any] = []
        for r in self.records:
            if hasattr(r, "to_dict") and callable(r.to_dict):
                items.append(r.to_dict())
            elif hasattr(r, "model_dump"):
                items.append(r.model_dump())
            else:
                items.append(r)
        return {
            "records": items,
            "total": self.total,
            "page": self.page,
            "size": self.size,
            "pages": self.pages,
            "current": self.current,
            "has_next": self.has_next,
            "has_prev": self.has_prev,
        }

    @classmethod
    def of(
        cls,
        records: Optional[List[T]] = None,
        total: int = 0,
        page: int = 1,
        size: int = 10,
    ) -> "Page[T]":
        return cls(records=records or [], total=total, page=page, size=size)

    @classmethod
    def empty(cls, page: int = 1, size: int = 10) -> "Page[T]":
        return cls(records=[], total=0, page=page, size=size)