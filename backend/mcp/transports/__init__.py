"""Transport layer для MCP."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class McpTransportConnector(Protocol):
    async def connect(self, client, *, headers: dict | None, timeout: float) -> None: ...
