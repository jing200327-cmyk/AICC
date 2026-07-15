"""
GLM Proxy Server — Anthropic Messages API → OpenAI Chat Completions API

Translates Claude Code's Anthropic-format requests into OpenAI-format for Zhipu GLM.
Supports: streaming, non-streaming, tool use, system prompts, multi-turn conversations.

Usage:  python server.py
        python server.py --port 18765
        python server.py --model glm-4-plus
"""

import argparse
import json
import logging
import os
import re
import sys
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from config_center.api import create_router as create_config_center_router
from config_center.service import ConfigCenterService
from daily_report.api import create_router as create_daily_report_router
from daily_report.service import DailyReportService

from lead_import.api import create_router
from lead_import.registry import StoreScriptRegistry
from lead_import.service import LeadImportService
from outcall.api import create_router as create_outcall_router
from outcall.service import OutcallService
from split_import.api import create_router as create_split_router
from split_import.service import SplitImportService
from task_records.api import create_router as create_task_records_router
from task_records.service import TaskRecordService

# ─── Config ───────────────────────────────────────────────────────────
API_KEY = os.environ.get("GLM_PROXY_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")


ZHIPU_BASE = os.environ.get(
    "GLM_PROXY_BASE_URL",
    "https://open.bigmodel.cn/api/coding/paas/v4"
)

UPSTREAM_MODEL = os.environ.get("GLM_PROXY_MODEL", "glm-4-plus")
LISTEN_PORT = int(os.environ.get("GLM_PROXY_PORT", "18765"))

# ─── Logging ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("glm-proxy")

# ─── FastAPI app ──────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(_app: FastAPI):
    await outcall_service.restore_running_jobs()
    yield


app = FastAPI(title="GLM Proxy", docs_url=None, redoc_url=None, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
LEAD_IMPORT_OUTPUT_DIR = os.environ.get(
    "LEAD_IMPORT_OUTPUT_DIR",
    os.path.join(BASE_DIR, "outputs", "lead-import"),
)
LEAD_IMPORT_INPUT_DIR = os.environ.get(
    "LEAD_IMPORT_INPUT_DIR",
    os.path.join(PROJECT_ROOT, "建银线索"),
)
lead_import_service = LeadImportService(
    registry=StoreScriptRegistry.default(),
    output_root=LEAD_IMPORT_OUTPUT_DIR,
    input_root=LEAD_IMPORT_INPUT_DIR,
)
app.include_router(create_router(lead_import_service))

AICC_ROOT = os.path.dirname(PROJECT_ROOT)
SPLIT_IMPORT_ROOT = os.environ.get(
    "SPLIT_IMPORT_ROOT",
    os.path.join(
        AICC_ROOT,
        "建银-线索自动预分割与导入脚本",
        "建银-线索自动预分割与导入脚本",
        "线索预分割",
    ),
)
split_import_service = SplitImportService(SPLIT_IMPORT_ROOT)
app.include_router(create_split_router(split_import_service))

OUTCALL_PROJECT_ROOT = os.environ.get(
    "OUTCALL_PROJECT_ROOT",
    os.path.join(AICC_ROOT, "建银-线索自动预分割与导入脚本", "建银-线索自动预分割与导入脚本"),
)
OUTCALL_CONFIG_PATH = os.environ.get(
    "OUTCALL_CONFIG_PATH",
    os.path.join(OUTCALL_PROJECT_ROOT, "config.yaml"),
)
OUTCALL_DB_PATH = os.environ.get(
    "OUTCALL_DB_PATH",
    os.path.join(BASE_DIR, "storage", "aicc.sqlite3"),
)
outcall_service = OutcallService(
    OUTCALL_CONFIG_PATH,
    OUTCALL_PROJECT_ROOT,
    split_import_service,
    OUTCALL_DB_PATH,
)
app.include_router(create_outcall_router(outcall_service))
DAILY_REPORT_PROJECT_ROOT = os.environ.get(
    "DAILY_REPORT_PROJECT_ROOT",
    os.path.join(AICC_ROOT, "龙星行报表工具_核心文件_260629"),
)
daily_report_service = DailyReportService(DAILY_REPORT_PROJECT_ROOT)
app.include_router(create_daily_report_router(daily_report_service))

task_record_service = TaskRecordService(lead_import_service, split_import_service, outcall_service, daily_report_service)
app.include_router(create_task_records_router(task_record_service))

config_center_service = ConfigCenterService(lead_import_service, split_import_service, OUTCALL_CONFIG_PATH, DAILY_REPORT_PROJECT_ROOT)
app.include_router(create_config_center_router(config_center_service))


@app.get("/aicc-frontend-demo.html")
async def aicc_frontend_demo():
    return FileResponse(os.path.join(AICC_ROOT, "aicc-frontend-demo.html"), media_type="text/html")


@app.get("/health")
async def health():
    return {"status": "ok", "upstream": UPSTREAM_MODEL, "port": LISTEN_PORT}


# ═══════════════════════════════════════════════════════════════════════
#  Request conversion:  Anthropic → OpenAI
# ═══════════════════════════════════════════════════════════════════════

def anthropic_to_openai(body: dict) -> dict:
    """Convert an Anthropic Messages request body into OpenAI Chat Completions format."""
    messages = []

    # ── system prompt (Anthropic top-level → OpenAI system message) ──
    system_text = _extract_system_text(body)
    if system_text:
        messages.append({"role": "system", "content": system_text})

    # ── conversation messages ──
    for msg in body.get("messages", []):
        converted = _convert_message(msg)
        if not converted:
            continue
        # A user message with tool_result blocks explodes into multiple
        # tool-role messages (one per result) plus an optional user-role text message
        if converted.get("_multi"):
            for tool_msg in converted.get("results", []):
                messages.append(tool_msg)
            if converted.get("_text"):
                messages.append({"role": "user", "content": converted["_text"]})
        else:
            messages.append(converted)

    openai_body = {
        "model": UPSTREAM_MODEL,
        "messages": messages,
        "max_tokens": body.get("max_tokens", 4096),
        "temperature": body.get("temperature", 0.7),
        "top_p": body.get("top_p", 0.95),
        "stream": body.get("stream", False),
    }

    # ── tools ──
    tools = body.get("tools")
    if tools:
        openai_body["tools"] = _convert_tools(tools)

    # ── stop sequences ──
    stop = body.get("stop_sequences")
    if stop:
        openai_body["stop"] = stop

    # ── optional: thinking / budget (Claude extended parameters) ──
    # Zhipu GLM doesn't support these; simply drop them.

    log.debug("→ OpenAI request: %s", json.dumps(openai_body, ensure_ascii=False, indent=2))
    return openai_body


def _extract_system_text(body: dict) -> str:
    """Extract system prompt from Anthropic body (top-level `system` field)."""
    system = body.get("system", "")
    if not system:
        return ""

    # Anthropic supports `system` as a string or an array of content blocks
    if isinstance(system, str):
        return system
    if isinstance(system, list):
        parts = []
        for block in system:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts)
    return str(system)


def _convert_message(msg: dict) -> Optional[dict]:
    """Convert a single Anthropic message to OpenAI format."""
    role = msg.get("role", "user")
    content = msg.get("content", "")

    # Anthropic `role` maps cleanly to OpenAI roles (user / assistant)
    # Anthropic content can be a plain string or a list of content blocks
    if isinstance(content, str):
        return {"role": role, "content": content}

    if not isinstance(content, list):
        return {"role": role, "content": str(content)}

    # ── content blocks array ──
    text_parts = []
    tool_calls = []
    tool_call_results = []

    for block in content:
        block_type = block.get("type", "")

        if block_type == "text":
            text_parts.append(block.get("text", ""))

        elif block_type == "tool_use":
            tool_calls.append({
                "id": block.get("id", f"call_{uuid.uuid4().hex[:12]}"),
                "type": "function",
                "function": {
                    "name": block.get("name", ""),
                    "arguments": json.dumps(block.get("input", {}), ensure_ascii=False),
                },
            })

        elif block_type == "tool_result":
            # tool_result blocks in Anthropic appear in user-role messages
            # → OpenAI `role: "tool"` message
            tc = block.get("tool_use_id", "")
            tc_content = block.get("content", "")
            if isinstance(tc_content, list):
                tc_content = "".join(
                    b.get("text", "") for b in tc_content if b.get("type") == "text"
                )
            tool_call_results.append({
                "role": "tool",
                "tool_call_id": tc,
                "content": str(tc_content),
            })

    # Assemble output
    if tool_calls and role == "assistant":
        return {
            "role": "assistant",
            "content": "\n".join(text_parts) if text_parts else None,
            "tool_calls": tool_calls,
        }

    if tool_call_results:
        return {
            "_multi": True,
            "results": tool_call_results,
            "_text": "\n".join(text_parts) if text_parts else "",
        }

    if text_parts:
        return {"role": role, "content": "\n".join(text_parts)}

    return None


def _convert_tools(tools: list) -> list:
    """Convert Anthropic tool definitions → OpenAI function tool definitions."""
    openai_tools = []
    for tool in tools:
        openai_tool = {
            "type": "function",
            "function": {
                "name": tool.get("name", ""),
                "description": tool.get("description", ""),
                "parameters": tool.get("input_schema", {"type": "object", "properties": {}}),
            },
        }
        openai_tools.append(openai_tool)
    return openai_tools


# ═══════════════════════════════════════════════════════════════════════
#  Response conversion:  OpenAI → Anthropic
# ═══════════════════════════════════════════════════════════════════════

def openai_to_anthropic(data: dict, request_id: str = "") -> dict:
    """Convert an OpenAI Chat Completions response → Anthropic Messages response."""
    choice = (data.get("choices") or [{}])[0]
    message = choice.get("message", {})
    usage = data.get("usage", {})

    # Build content blocks
    content = []

    # text
    text = message.get("content", "")
    if text:
        content.append({"type": "text", "text": text})

    # tool calls
    for tc in message.get("tool_calls", []):
        fn = tc.get("function", {})
        try:
            tool_input = json.loads(fn.get("arguments", "{}"))
        except json.JSONDecodeError:
            tool_input = {}
        content.append({
            "type": "tool_use",
            "id": tc.get("id", f"call_{uuid.uuid4().hex[:12]}"),
            "name": fn.get("name", ""),
            "input": tool_input,
        })

    finish_reason = choice.get("finish_reason", "stop")
    stop_reason = _map_finish_to_stop(finish_reason, content)

    anthropic_resp = {
        "id": data.get("id", f"msg_{uuid.uuid4().hex}"),
        "type": "message",
        "role": "assistant",
        "content": content,
        "model": UPSTREAM_MODEL,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        },
    }

    log.debug("← Anthropic response: %s", json.dumps(anthropic_resp, ensure_ascii=False, indent=2))
    return anthropic_resp


def _map_finish_to_stop(finish_reason: str, content: list) -> str:
    """Map OpenAI finish_reason → Anthropic stop_reason."""
    if finish_reason == "stop":
        return "end_turn"
    if finish_reason == "tool_calls":
        return "tool_use"
    if finish_reason == "length":
        return "max_tokens"
    if finish_reason == "content_filter":
        return "end_turn"
    return "end_turn"


# ═══════════════════════════════════════════════════════════════════════
#  Streaming  (OpenAI SSE → Anthropic SSE)
# ═══════════════════════════════════════════════════════════════════════

async def stream_response(openai_body: dict, request_id: str = ""):
    """Call Zhipu with streaming, convert SSE chunks into Anthropic SSE events."""
    msg_id = f"msg_{uuid.uuid4().hex[:16]}"
    model = UPSTREAM_MODEL
    accumulated_text = ""
    accumulated_tool_calls: dict = {}  # index → {id, name, arguments}

    async with httpx.AsyncClient(timeout=180.0) as client:
        try:
            async with client.stream(
                "POST",
                f"{ZHIPU_BASE}/chat/completions",
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json",
                },
                json=openai_body,
            ) as resp:
                if resp.status_code != 200:
                    error_text = await resp.aread()
                    log.error("Zhipu streaming error %d: %s", resp.status_code, error_text)
                    yield _sse_event("error", {
                        "type": "error",
                        "error": {"type": "api_error", "message": f"Upstream {resp.status_code}: {error_text.decode()}"},
                    })
                    return

                # ── message_start ──
                yield _sse_event("message_start", {
                    "type": "message_start",
                    "message": {
                        "id": msg_id,
                        "type": "message",
                        "role": "assistant",
                        "content": [],
                        "model": model,
                        "stop_reason": None,
                        "stop_sequence": None,
                        "usage": {"input_tokens": 0, "output_tokens": 0},
                    },
                })

                content_block_index = 0
                current_block_started = False
                stop_reason = None
                usage_info = {"input_tokens": 0, "output_tokens": 0}

                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue

                    data_str = line[len("data: "):]
                    if data_str == "[DONE]":
                        break

                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    delta_choice = (chunk.get("choices") or [{}])[0]
                    delta = delta_choice.get("delta", {})
                    finish = delta_choice.get("finish_reason")
                    chunk_usage = chunk.get("usage")

                    # ── text ──
                    text_content = delta.get("content", "")
                    if text_content:
                        if not current_block_started:
                            # Anthropic content_block_start (text)
                            yield _sse_event("content_block_start", {
                                "type": "content_block_start",
                                "index": content_block_index,
                                "content_block": {"type": "text", "text": ""},
                            })
                            current_block_started = True

                        accumulated_text += text_content
                        yield _sse_event("content_block_delta", {
                            "type": "content_block_delta",
                            "index": content_block_index,
                            "delta": {"type": "text_delta", "text": text_content},
                        })

                    # ── tool calls ──
                    for tc in delta.get("tool_calls", []):
                        idx = tc.get("index", 0)
                        if idx not in accumulated_tool_calls:
                            accumulated_tool_calls[idx] = {
                                "id": tc.get("id", f"call_{uuid.uuid4().hex[:12]}"),
                                "name": tc.get("function", {}).get("name", ""),
                                "arguments": "",
                            }

                        fn = tc.get("function", {})
                        if fn.get("name"):
                            accumulated_tool_calls[idx]["name"] = fn["name"]
                        if fn.get("arguments"):
                            accumulated_tool_calls[idx]["arguments"] += fn["arguments"]

                    # ── finish ──
                    if finish:
                        # Close current content block if open
                        if current_block_started:
                            yield _sse_event("content_block_stop", {
                                "type": "content_block_stop",
                                "index": content_block_index,
                            })
                            current_block_started = False
                            content_block_index += 1

                        # Emit tool_use blocks at end
                        for idx in sorted(accumulated_tool_calls.keys()):
                            tc = accumulated_tool_calls[idx]
                            try:
                                tool_input = json.loads(tc["arguments"]) if tc["arguments"] else {}
                            except json.JSONDecodeError:
                                tool_input = {"raw": tc["arguments"]}

                            yield _sse_event("content_block_start", {
                                "type": "content_block_start",
                                "index": content_block_index,
                                "content_block": {
                                    "type": "tool_use",
                                    "id": tc["id"],
                                    "name": tc["name"],
                                    "input": {},
                                },
                            })
                            yield _sse_event("content_block_delta", {
                                "type": "content_block_delta",
                                "index": content_block_index,
                                "delta": {
                                    "type": "input_json_delta",
                                    "partial_json": tc["arguments"],
                                },
                            })
                            yield _sse_event("content_block_stop", {
                                "type": "content_block_stop",
                                "index": content_block_index,
                            })
                            content_block_index += 1

                        stop_reason = _map_finish_to_stop(finish, [])
                        if chunk_usage:
                            usage_info = {
                                "input_tokens": chunk_usage.get("prompt_tokens", 0),
                                "output_tokens": chunk_usage.get("completion_tokens", 0),
                            }

                    # Handle usage-only chunks (no delta content)
                    if chunk_usage and not finish and not text_content and not delta.get("tool_calls"):
                        usage_info = {
                            "input_tokens": chunk_usage.get("prompt_tokens", 0),
                            "output_tokens": chunk_usage.get("completion_tokens", 0),
                        }

                # ── message_delta ──
                yield _sse_event("message_delta", {
                    "type": "message_delta",
                    "delta": {"stop_reason": stop_reason or "end_turn", "stop_sequence": None},
                    "usage": {
                        "input_tokens": usage_info.get("input_tokens", 0),
                        "output_tokens": usage_info.get("output_tokens", 0),
                    },
                })

                # ── message_stop ──
                yield _sse_event("message_stop", {"type": "message_stop"})

        except httpx.ReadTimeout:
            log.error("Zhipu streaming timed out")
            yield _sse_event("error", {
                "type": "error",
                "error": {"type": "timeout", "message": "Upstream request timed out"},
            })
        except Exception as exc:
            log.exception("Streaming error")
            yield _sse_event("error", {
                "type": "error",
                "error": {"type": "internal_error", "message": str(exc)},
            })


def _sse_event(event: str, data: dict) -> str:
    """Format an SSE event in Anthropic's wire format."""
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


# ═══════════════════════════════════════════════════════════════════════
#  Route:  POST /v1/messages   (the ONLY Anthropic endpoint we need)
# ═══════════════════════════════════════════════════════════════════════

@app.post("/v1/messages")
async def messages_endpoint(request: Request):
    """
    Anthropic Messages API → Zhipu GLM Chat Completions.

    Claude Code hits this endpoint for every model interaction.
    We translate the request, call Zhipu, and translate the response back.
    """
    request_id = f"req_{uuid.uuid4().hex[:8]}"
    if not API_KEY:
        return JSONResponse(
            {"type": "error", "error": {"type": "authentication_error", "message": "Missing GLM_PROXY_API_KEY or ANTHROPIC_AUTH_TOKEN"}},
            status_code=401,
        )

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"type": "error", "error": {"type": "invalid_request_error", "message": "Invalid JSON body"}},
            status_code=400,
        )

    stream = body.get("stream", False)
    model_sent = body.get("model", "?")
    log.info("[%s] %s %s  stream=%s  model_sent=%s", request_id, request.method, request.url.path, stream, model_sent)

    try:
        openai_body = anthropic_to_openai(body)
    except Exception as exc:
        log.exception("[%s] Request conversion failed", request_id)
        return JSONResponse(
            {"type": "error", "error": {"type": "invalid_request_error", "message": f"Conversion error: {exc}"}},
            status_code=400,
        )

    if stream:
        return StreamingResponse(
            stream_response(openai_body, request_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # ── non-streaming ──
    async with httpx.AsyncClient(timeout=180.0) as client:
        try:
            resp = await client.post(
                f"{ZHIPU_BASE}/chat/completions",
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json",
                },
                json=openai_body,
            )
            if resp.status_code != 200:
                log.error("[%s] Upstream error %d: %s", request_id, resp.status_code, resp.text)
                return JSONResponse(
                    {
                        "type": "error",
                        "error": {
                            "type": "api_error",
                            "message": f"Zhipu API returned {resp.status_code}: {resp.text[:500]}",
                        },
                    },
                    status_code=502,
                )

            data = resp.json()
            anthropic_resp = openai_to_anthropic(data, request_id)
            log.info("[%s] OK  tokens_in=%d  tokens_out=%d",
                     request_id,
                     anthropic_resp.get("usage", {}).get("input_tokens", 0),
                     anthropic_resp.get("usage", {}).get("output_tokens", 0))
            return JSONResponse(anthropic_resp)

        except httpx.ReadTimeout:
            log.error("[%s] Upstream timeout", request_id)
            return JSONResponse(
                {"type": "error", "error": {"type": "timeout", "message": "Upstream request timed out"}},
                status_code=504,
            )
        except Exception as exc:
            log.exception("[%s] Unexpected error", request_id)
            return JSONResponse(
                {"type": "error", "error": {"type": "internal_error", "message": str(exc)}},
                status_code=500,
            )


# ═══════════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════════

def main():
    global LISTEN_PORT, UPSTREAM_MODEL

    parser = argparse.ArgumentParser(description="GLM Proxy — Anthropic ↔ OpenAI translation layer")
    parser.add_argument("--port", type=int, default=LISTEN_PORT, help="Listen port (default: %(default)s)")
    parser.add_argument("--model", type=str, default=UPSTREAM_MODEL, help="Upstream GLM model (default: %(default)s)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    LISTEN_PORT = args.port
    UPSTREAM_MODEL = args.model
    if args.debug:
        log.setLevel(logging.DEBUG)

    log.info("=" * 60)
    log.info("GLM Proxy starting")
    log.info("  Listen:        http://127.0.0.1:%d", LISTEN_PORT)
    log.info("  Upstream:      %s", ZHIPU_BASE)
    log.info("  Upstream model: %s", UPSTREAM_MODEL)
    log.info("=" * 60)

    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=LISTEN_PORT, log_level="warning")


if __name__ == "__main__":
    main()


