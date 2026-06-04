from dataclasses import dataclass
from pathlib import Path

from app.core.storage import read_json, utc_now_iso, write_json
from app.core.targets import TARGETS_PATH
from app.core.training import MODEL_REGISTRY_PATH, get_current_model, train_target_model


PUBLICATION_GOAL = 39


@dataclass
class PublicationEligibility:
    target: str
    status: str
    publish: bool
    eligible: bool
    reasons: list[str]
    has_active_model: bool
    adopted: bool
    improvement_rate: float | None
    cv_mae: float | None


@dataclass
class PromotionResult:
    target: str
    promoted: bool
    message: str


def get_publication_plan() -> dict[str, object]:
    targets = _load_targets()
    published = [t for t in targets if t.get("publish") and t.get("status") != "blocked"]
    ready_published = [t for t in published if t.get("status") == "ready"]
    beta_published = [t for t in published if t.get("status") == "beta"]
    candidates = list_publication_candidates()

    return {
        "goal": PUBLICATION_GOAL,
        "published_count": len(published),
        "remaining_slots": max(0, PUBLICATION_GOAL - len(published)),
        "ready_published": len(ready_published),
        "beta_published": len(beta_published),
        "beta_candidates_eligible": len([c for c in candidates if c.eligible]),
        "beta_candidates_total": len(candidates),
        "updated_at": utc_now_iso(),
    }


def evaluate_publication_eligibility(target: str) -> PublicationEligibility:
    row = _find_target(target)
    if row is None:
        raise ValueError(f"Target '{target}' not found.")

    status = str(row.get("status"))
    publish = bool(row.get("publish"))
    reasons: list[str] = []
    has_active = False
    adopted = False
    improvement_rate: float | None = None
    cv_mae: float | None = None

    if status == "blocked":
        reasons.append("Target is blocked.")
    elif status not in {"ready", "beta"}:
        reasons.append(f"Unsupported status '{status}'.")

    try:
        model_entry = get_current_model(target)
        has_active = True
        evaluation = model_entry.get("evaluation") or {}
        adopted = bool(evaluation.get("adopted", False))
        improvement_rate = _as_float(evaluation.get("improvement_rate"))
        cv_mae = _as_float(evaluation.get("cv_mae"))
        if not adopted:
            reasons.append("Active model is not adopted (below baseline improvement threshold).")
    except ValueError:
        reasons.append("No active model. Train with auto_steps first.")

    if publish:
        reasons.append("Already published.")

    eligible = len(reasons) == 0
    return PublicationEligibility(
        target=target,
        status=status,
        publish=publish,
        eligible=eligible,
        reasons=reasons,
        has_active_model=has_active,
        adopted=adopted,
        improvement_rate=improvement_rate,
        cv_mae=cv_mae,
    )


def list_publication_candidates() -> list[PublicationEligibility]:
    targets = _load_targets()
    beta_rows = [t for t in targets if t.get("status") == "beta"]
    candidates: list[PublicationEligibility] = []
    for row in beta_rows:
        item = evaluate_publication_eligibility(str(row["target"]))
        candidates.append(item)
    candidates.sort(
        key=lambda item: (
            not item.eligible,
            item.improvement_rate is None,
            -(item.improvement_rate or 0.0),
            item.cv_mae if item.cv_mae is not None else float("inf"),
        )
    )
    return candidates


def promote_target(target: str, reason: str, force: bool = False) -> PromotionResult:
    eligibility = evaluate_publication_eligibility(target)
    if eligibility.publish:
        return PromotionResult(target=target, promoted=False, message="Already published.")
    if not eligibility.eligible and not force:
        return PromotionResult(
            target=target,
            promoted=False,
            message="; ".join(eligibility.reasons) or "Not eligible.",
        )

    plan = get_publication_plan()
    if int(plan["remaining_slots"]) <= 0 and not force:
        return PromotionResult(
            target=target,
            promoted=False,
            message=f"Publication goal ({PUBLICATION_GOAL}) already reached.",
        )

    _set_publish(target, publish=True, reason=reason)
    return PromotionResult(target=target, promoted=True, message="Published.")


def promote_eligible_beta(*, limit: int | None = None, reason: str = "beta quality gate passed") -> dict[str, object]:
    plan = get_publication_plan()
    remaining = int(plan["remaining_slots"])
    if remaining <= 0:
        return {
            "promoted": [],
            "skipped": [],
            "message": f"Publication goal ({PUBLICATION_GOAL}) already reached.",
        }

    max_promotions = remaining if limit is None else min(remaining, limit)
    promoted: list[str] = []
    skipped: list[dict[str, str]] = []

    for candidate in list_publication_candidates():
        if len(promoted) >= max_promotions:
            break
        if not candidate.eligible:
            skipped.append({"target": candidate.target, "reason": "; ".join(candidate.reasons)})
            continue
        result = promote_target(candidate.target, reason=reason)
        if result.promoted:
            promoted.append(candidate.target)
        else:
            skipped.append({"target": candidate.target, "reason": result.message})

    return {
        "goal": PUBLICATION_GOAL,
        "promoted": promoted,
        "skipped": skipped,
        "promoted_count": len(promoted),
        "plan": get_publication_plan(),
        "at": utc_now_iso(),
    }


def train_beta_candidates() -> dict[str, list[dict[str, object]]]:
    targets = [t for t in _load_targets() if t.get("status") == "beta"]
    results: list[dict[str, object]] = []
    errors: list[dict[str, object]] = []
    for row in targets:
        target = str(row["target"])
        try:
            trained = train_target_model(target, feature_profile="auto_steps", strategy="auto")
            results.append(
                {
                    "target": trained.target,
                    "model_version": trained.model_version,
                    "feature_profile": trained.feature_profile,
                    "adopted": trained.adopted,
                    "improvement_rate": trained.evaluation.improvement_rate,
                    "cv_mae": trained.evaluation.cv_mae,
                }
            )
        except Exception as exc:
            errors.append({"target": target, "error": str(exc)})
    return {"results": results, "errors": errors}


def _load_targets() -> list[dict[str, object]]:
    if not TARGETS_PATH.exists():
        return []
    return read_json(TARGETS_PATH).get("targets", [])


def _find_target(target: str) -> dict[str, object] | None:
    for row in _load_targets():
        if row.get("target") == target:
            return row
    return None


def _set_publish(target: str, publish: bool, reason: str) -> None:
    if not TARGETS_PATH.exists():
        raise ValueError("Targets registry not found.")
    payload = read_json(TARGETS_PATH)
    found = False
    for item in payload.get("targets", []):
        if item.get("target") != target:
            continue
        found = True
        if item.get("status") == "blocked" and publish:
            raise ValueError("Blocked target cannot be published.")
        item["publish"] = publish
        item["updated_at"] = utc_now_iso()
        break
    if not found:
        raise ValueError(f"Target '{target}' not found.")
    payload["updated_at"] = utc_now_iso()
    write_json(TARGETS_PATH, payload)


def _as_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
