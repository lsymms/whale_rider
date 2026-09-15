"""HTTP routes for local fakes and deterministic domain operations."""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Request

from backend.domain.alerts.engine import AlertEngine, AlertRule, MarketEvent, RuleTemplate
from backend.domain.positions import VersionConflict
from backend.storage import RuleConflict, RuleNotFound, RuleStore

from .service import LocalApiService, decimal_text, parse_datetime, required_text, utc_now


router = APIRouter(prefix="/api/v1")


def service(request: Request) -> LocalApiService:
    return request.app.state.local_api


def failure(error: Exception) -> HTTPException:
    return HTTPException(status_code=422, detail={"code": "validation_error", "message": str(error)})


def rules(request: Request) -> RuleStore:
    return RuleStore(request.app.state.database)


def rule_view(value: object) -> dict[str, object]:
    return {"rule_id": value.rule_id, "revision": value.revision, "state": value.state, "paused_until": value.paused_until.isoformat() if value.paused_until else None, "rule": dict(value.payload)}


@router.get("/rules")
async def list_rules(request: Request) -> list[dict[str, object]]:
    return [rule_view(value) for value in rules(request).list()]


@router.post("/rules", status_code=201)
async def create_rule(payload: dict[str, object], request: Request) -> dict[str, object]:
    try:
        rule_id = required_text(payload, "rule_id")
        return rule_view(rules(request).create(rule_id, payload))
    except (ValueError, RuleConflict) as error:
        raise failure(error) from error


@router.patch("/rules/{rule_id}")
async def revise_rule(rule_id: str, payload: dict[str, object], request: Request) -> dict[str, object]:
    try:
        match = request.headers.get("if-match")
        if match is None:
            raise ValueError("If-Match revision header is required")
        return rule_view(rules(request).revise(rule_id, int(match), payload))
    except RuleNotFound as error:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "rule not found"}) from error
    except (ValueError, RuleConflict) as error:
        status = 409 if isinstance(error, RuleConflict) else 422
        raise HTTPException(status_code=status, detail={"code": "revision_conflict" if status == 409 else "validation_error", "message": str(error)}) from error


@router.post("/rules/{rule_id}/pause")
async def pause_rule(rule_id: str, payload: dict[str, object], request: Request) -> dict[str, object]:
    try:
        until = parse_datetime(payload["until"], utc_now()) if payload.get("until") is not None else None
        return rule_view(rules(request).pause(rule_id, until))
    except RuleNotFound as error:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "rule not found"}) from error
    except (ValueError, RuleConflict) as error:
        raise failure(error) from error


@router.post("/rules/{rule_id}/archive")
async def archive_rule(rule_id: str, request: Request) -> dict[str, object]:
    try:
        return rule_view(rules(request).archive(rule_id))
    except RuleNotFound as error:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "rule not found"}) from error


@router.get("/capabilities")
async def capabilities(request: Request) -> dict[str, object]:
    return service(request).capabilities()


@router.post("/capabilities/probe")
async def probe_capabilities(request: Request) -> dict[str, object]:
    """Explicit read-only operator action; never invoked by startup or GET status."""
    try:
        return service(request).refresh_capabilities()
    except ValueError as error:
        raise failure(error) from error


@router.post("/rules/simulate")
async def simulate_rule(payload: dict[str, object]) -> dict[str, object]:
    try:
        raw_rule = payload["rule"]
        raw_event = payload["event"]
        if not isinstance(raw_rule, dict) or not isinstance(raw_event, dict):
            raise ValueError("rule and event must be objects")
        rule = AlertRule(
            rule_id=required_text(raw_rule, "rule_id"), template=RuleTemplate(required_text(raw_rule, "template")),
            asset_type=required_text(raw_rule, "asset_type"), universe=frozenset(str(value) for value in raw_rule.get("universe", [])),
            minimum_quantity=Decimal(required_text(raw_rule, "minimum_quantity")), minimum_notional=Decimal(required_text(raw_rule, "minimum_notional")),
            qualifying_minimum_notional=Decimal(str(raw_rule["qualifying_minimum_notional"])) if raw_rule.get("qualifying_minimum_notional") is not None else None,
            cooldown=timedelta(seconds=int(raw_rule.get("cooldown_seconds", 60))),
            held_underlyings=frozenset(str(value) for value in raw_rule.get("held_underlyings", [])),
        )
        event = MarketEvent(
            event_id=required_text(raw_event, "event_id"), instrument_id=required_text(raw_event, "instrument_id"), underlying=required_text(raw_event, "underlying"),
            asset_type=required_text(raw_event, "asset_type"), event_type=required_text(raw_event, "event_type"),
            event_time=parse_datetime(raw_event.get("event_time"), utc_now()), quantity=Decimal(required_text(raw_event, "quantity")), price=Decimal(required_text(raw_event, "price")),
            price_multiplier=Decimal(str(raw_event["price_multiplier"])) if raw_event.get("price_multiplier") is not None else None,
            multiplier_verified=bool(raw_event.get("multiplier_verified", False)), identity_reliable=bool(raw_event.get("identity_reliable", False)),
        )
        outcome = AlertEngine().evaluate(rule, event)
        return {"mode": "dry_run", "code": outcome.code.value, "triggered": outcome.triggered, "notional": decimal_text(outcome.notional), "enrichment_only": outcome.enrichment_only}
    except (KeyError, ValueError, ArithmeticError) as error:
        raise failure(error) from error


@router.post("/imports", status_code=202)
async def create_import(payload: dict[str, object], request: Request) -> dict[str, object]:
    try:
        draft = service(request).create_draft(payload)
        return draft_view(draft)
    except (ValueError, ArithmeticError) as error:
        raise failure(error) from error


@router.patch("/imports/{import_id}/rows")
async def review_import(import_id: str, payload: dict[str, object], request: Request) -> dict[str, object]:
    try:
        return draft_view(service(request).update_draft(import_id, payload))
    except KeyError as error:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "import draft not found"}) from error
    except (ValueError, ArithmeticError) as error:
        raise failure(error) from error


@router.post("/imports/{import_id}/commit")
async def commit_import(import_id: str, request: Request) -> dict[str, object]:
    try:
        return snapshot_view(service(request).commit_draft(import_id))
    except KeyError as error:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "import draft not found"}) from error
    except VersionConflict as error:
        raise HTTPException(status_code=409, detail={"code": "version_conflict", "message": str(error)}) from error
    except (ValueError, ArithmeticError) as error:
        raise failure(error) from error


@router.get("/positions/{account_id}")
async def positions(account_id: str, request: Request) -> dict[str, object]:
    try:
        return snapshot_view(service(request).current_snapshot(account_id))
    except KeyError as error:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "position snapshot not found"}) from error


@router.get("/positions/{account_id}/exposure")
async def exposure(account_id: str, request: Request) -> dict[str, object]:
    try:
        return service(request).exposure(account_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "position snapshot not found"}) from error


@router.post("/suggestions")
async def suggestions(payload: dict[str, object], request: Request) -> dict[str, object]:
    try:
        return service(request).suggestions(required_text(payload, "account_id"))
    except KeyError as error:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "position snapshot not found"}) from error
    except ValueError as error:
        raise failure(error) from error


def draft_view(draft: object) -> dict[str, object]:
    return {
        "import_id": draft.import_id, "account_id": draft.account_id, "expected_position_version": draft.expected_version,
        "status": "review_required" if draft.review_required else "ready_for_commit", "row_count": len(draft.rows),
    }


def snapshot_view(snapshot: object) -> dict[str, object]:
    return {
        "account_id": snapshot.account_id, "version": snapshot.version, "source": snapshot.source.value, "complete": snapshot.complete,
        "positions": [
            {"instrument_id": item.instrument_id, "underlying": item.underlying, "asset_type": item.asset_type, "quantity": decimal_text(item.quantity)}
            for item in snapshot.positions
        ],
    }
