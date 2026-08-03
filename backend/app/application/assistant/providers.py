"""Rule-based assistant provider — the V1 adapter of the AssistantProvider port.

Entirely local and deterministic: the intent parser routes the question to a
builder, and every builder is a READ-ONLY composition over the frozen modules'
own computations — ``ProductivitySnapshot`` + ``build_calendar_feed`` /
``build_reminders`` (productivity), ``build_attendance_summary`` (teaching),
``events_dashboard`` (events), ``reports_dashboard`` / per-kind report use
cases (reports) — plus the universal ObjectRepository port with the frozen
metadata keys. Nothing is duplicated, nothing external is called.

Answer contract: one plain-language summary (deterministic template), KPI
metrics, typed context cards (linked to the existing module pages), suggested
actions, and the source modules consulted — the brief's PART 3/4/5 surface.
"""
from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass

from app.application.assistant.intents import ParsedQuestion, parse_question
from app.application.dtos import assistant as dto
from app.application.dtos.events import (
    ATTENDEE_ROLES,
    KEY_EVENT_STATUS,
    KEY_EVENT_TYPE,
    KEY_PARTICIPATION,
    KEY_REGISTRATION,
    ORGANIZER_ROLES,
    UPCOMING_EVENT_STATUSES,
)
from app.application.dtos.finance import (
    ACTIVE_PROPOSAL_STATUSES,
    KEY_BILLS,
    KEY_ESTIMATED_COST,
    KEY_PROPOSAL_STATUS,
    KEY_PURCHASE_ORDERS,
)
from app.application.dtos.publication import (
    KEY_CONFERENCE,
    KEY_PUBLICATION_TYPE,
)
from app.application.dtos.publication import (
    KEY_DATE as KEY_PUB_DATE,
)
from app.application.dtos.publication import (
    KEY_YEAR as KEY_PUB_YEAR,
)
from app.application.dtos.reports import REPORT_TITLES, fmt_money
from app.application.dtos.research import (
    KEY_AMOUNT,
    KEY_LIFECYCLE_STATUS,
    PROJECT_IN_FLIGHT_STATUSES,
    parse_amount,
)
from app.application.dtos.teaching import parse_json_object
from app.application.queries.get_productivity_dashboard import GetProductivityDashboardQuery
from app.application.use_cases.events.helpers import events_dashboard
from app.application.use_cases.productivity.get_dashboard import GetProductivityDashboardUseCase
from app.application.use_cases.productivity.helpers import (
    ProductivitySnapshot,
    add_days,
    build_calendar_feed,
    build_reminders,
    personal_tasks,
    task_is_done,
    today_iso,
    token_match,
)
from app.application.use_cases.reports.get_dashboard import reports_dashboard
from app.application.use_cases.teaching.attendance_summary import build_attendance_summary
from app.application.use_cases.teaching.helpers import (
    attendance_sessions_of_class,
    enrolled_students,
)
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType, RelationshipKind

PROVIDER_NAME = "rules-v1"
DEFAULT_ASKER = "system"
# report-output envelope keys that must not leak into headline metrics
_REPORT_NOISE_KEYS = {
    "kind", "title", "generated_at", "generated_by", "filters", "scope",
    "params", "as_of", "academic_year", "institution",
}

# object_type -> frontend detail route pattern (the CalendarItem.href doctrine)
TYPE_HREFS: dict[str, str] = {
    "publication": "/publications/{id}",
    "research_project": "/research/projects/{id}",
    "grant": "/research/grants/{id}",
    "funding_agency": "/research/agencies",
    "faculty": "/faculty/{id}",
    "student": "/students/{id}",
    "course": "/teaching/classes/{id}",
    "assignment": "/teaching/assignments/{id}",
    "submission": "/teaching/assignments/{id}",
    "vendor": "/finance/vendors",
    "purchase": "/finance/{id}",
    "event": "/events/{id}",
    "committee": "/committees/{id}",
    "meeting": "/committees/meetings/{id}",
    "document": "/documents/{id}",
    "task": "/productivity",
    "notification": "/productivity",
}


def _meta(obj: UniversalObject) -> dict[str, str]:
    return {entry.key: entry.value for entry in obj.metadata.entries}


def _json_list(raw: str | None) -> list:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        return []
    return value if isinstance(value, list) else []


def _href_for(object_type: str, object_id: str) -> str:
    pattern = TYPE_HREFS.get(object_type, "/objects/{id}")
    return pattern.format(id=object_id)


def _card(obj: UniversalObject, subtitle: str | None = None, badge: str | None = None,
          stats: dict[str, str] | None = None, href: str | None = None) -> dto.AssistantCardOutput:
    object_id = str(obj.id)
    object_type = obj.object_type.value
    return dto.AssistantCardOutput(
        object_id=object_id,
        object_type=object_type,
        title=obj.title,
        subtitle=subtitle,
        href=href or _href_for(object_type, object_id),
        badge=badge,
        stats=stats or {},
    )


def _money(value: float) -> str:
    """INR display — reuses the Reports module platform convention (en-IN
    grouping); nothing is re-implemented here."""
    return fmt_money(value)


def _sort_by_meta_date(objs: list[UniversalObject], *keys: str, reverse: bool = True) -> list[UniversalObject]:
    def key_fn(obj: UniversalObject):
        meta = _meta(obj)
        stamp = next((meta.get(key) for key in keys if meta.get(key)), "")
        created = getattr(getattr(obj, "audit", None), "created_at", None)
        return (stamp or (created.isoformat() if created else ""), obj.title.lower())

    return sorted(objs, key=key_fn, reverse=reverse)


def _cap(items: list, limit: int = dto.ANSWER_CARD_LIMIT) -> list:
    return items[:limit]


class RuleBasedAssistantProvider:
    """V1 provider: deterministic intent → read-only cross-module builders."""

    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    @property
    def name(self) -> str:
        return PROVIDER_NAME

    # ------------------------------------------------------------------ entry
    def answer(self, question: str, asked_by: str = DEFAULT_ASKER) -> dto.AssistantAnswerOutput:
        parsed = parse_question(question)
        builder = getattr(self, f"_answer_{parsed.intent}", None) or self._answer_knowledge_search
        answer = builder(parsed, question, asked_by)
        if not answer.actions:
            answer.actions = self._default_actions(answer.intent)
        return answer

    # ------------------------------------------------------------------ frame
    def _base(self, parsed: ParsedQuestion, question: str, summary: str,
              sources: list[str], metrics: dict[str, str] | None = None,
              items: list[dict] | None = None, cards: list[AssistantCardT] | None = None,
              actions: list[dto.AssistantActionOutput] | None = None) -> dto.AssistantAnswerOutput:
        return dto.AssistantAnswerOutput(
            intent=parsed.intent,
            intent_label=dto.INTENT_LABELS.get(parsed.intent, parsed.intent),
            question=question.strip(),
            summary=summary,
            metrics=metrics or {},
            items=items or [],
            cards=cards or [],
            actions=actions or [],
            sources=sources,
        )

    def _default_actions(self, intent: str) -> list[dto.AssistantActionOutput]:
        module = {
            "projects": "/research", "grants": "/research", "publications": "/publications",
        }.get(intent)
        href = module or "/assistant"
        return [dto.AssistantActionOutput(label="Open module", href=href, kind="module")]

    def _snapshot(self) -> ProductivitySnapshot:
        return ProductivitySnapshot(self._repository)

    def _feed_cards(self, snapshot: ProductivitySnapshot, sources: tuple[str, ...],
                    date_from: str, date_to: str, today: str) -> list[dto.AssistantCardOutput]:
        feed = build_calendar_feed(snapshot, date_from, date_to, sources, today)
        cards: list[dto.AssistantCardOutput] = []
        for item in _cap(feed):
            subtitle = item.date + (f" {item.start_time}" if item.start_time else "")
            if item.subtitle:
                subtitle = f"{subtitle} · {item.subtitle}"
            cards.append(dto.AssistantCardOutput(
                object_id=item.source_id,
                object_type=item.source,
                title=item.title,
                subtitle=subtitle,
                href=item.href,
                badge=item.kind,
                stats={"status": item.status or ""},
            ))
        return cards

    # ------------------------------------------------------------- dashboard
    def _answer_today_plan(self, parsed, question, asked_by) -> dto.AssistantAnswerOutput:
        snapshot = self._snapshot()
        dash = GetProductivityDashboardUseCase(self._repository).execute(
            GetProductivityDashboardQuery()
        )
        today = today_iso()
        buckets = build_reminders(snapshot, today)
        summary = (
            f"Today you have {dash.todays_tasks} task(s) due, {dash.unread_notifications} unread "
            f"notification(s) and {dash.overdue_items} overdue item(s). This week brings "
            f"{dash.upcoming_deadlines} deadline(s) and {dash.upcoming_meetings} meeting(s)."
        )
        metrics = {
            "Tasks due today": str(dash.todays_tasks),
            "Overdue": str(dash.overdue_items),
            "Meetings (7d)": str(dash.upcoming_meetings),
            "Deadlines (7d)": str(dash.upcoming_deadlines),
        }
        items = [
            {"title": f"[{bucket}] {item.title}", "subtitle": item.date, "href": item.href}
            for bucket in ("overdue", "due_today", "upcoming_today", "tomorrow")
            for item in buckets[bucket]
        ]
        cards = [
            dto.AssistantCardOutput(
                object_id=item.id.split(":", 1)[-1], object_type=item.source,
                title=item.title, subtitle=f"{item.date} · {bucket.replace('_', ' ')}",
                href=item.href, badge=bucket,
            )
            for bucket in ("overdue", "due_today", "upcoming_today")
            for item in buckets[bucket]
        ]
        return self._base(parsed, question, summary, ["productivity", "calendar"],
                          metrics=metrics, items=_cap(items), cards=_cap(cards),
                          actions=[dto.AssistantActionOutput("Open Productivity Hub", "/productivity", "module")])

    def _answer_pending_items(self, parsed, question, asked_by) -> dto.AssistantAnswerOutput:
        snapshot = self._snapshot()
        today = today_iso()
        buckets = build_reminders(snapshot, today)
        open_tasks = [t for t in personal_tasks(snapshot.tasks_all) if not task_is_done(t)]
        overdue = buckets["overdue"]
        summary = (
            f"{len(open_tasks)} open personal task(s), {len(overdue)} overdue item(s) and "
            f"{len(buckets['this_week'])} item(s) due this week across your modules."
        )
        cards = [
            dto.AssistantCardOutput(
                object_id=item.id.split(":", 1)[-1], object_type=item.source,
                title=item.title, subtitle=f"{item.date} · {bucket.replace('_', ' ')}",
                href=item.href, badge=bucket,
            )
            for bucket in ("overdue", "due_today", "upcoming_today", "tomorrow", "this_week")
            for item in buckets[bucket]
        ]
        return self._base(parsed, question, summary, ["productivity"],
                          metrics={"Open tasks": str(len(open_tasks)), "Overdue": str(len(overdue))},
                          cards=_cap(cards),
                          actions=[dto.AssistantActionOutput("Open Productivity Hub", "/productivity", "module")])

    def _answer_upcoming_deadlines(self, parsed, question, asked_by) -> dto.AssistantAnswerOutput:
        snapshot = self._snapshot()
        today = today_iso()
        buckets = build_reminders(snapshot, today)
        rows = list(buckets["overdue"]) + list(buckets["due_today"]) + \
            list(buckets["tomorrow"]) + list(buckets["this_week"])
        summary = (
            f"{len(buckets['overdue'])} overdue item(s), {len(buckets['tomorrow'])} tomorrow and "
            f"{len(buckets['this_week'])} more this week."
        )
        cards = [
            dto.AssistantCardOutput(
                object_id=item.id.split(":", 1)[-1], object_type=item.source,
                title=item.title, subtitle=item.date, href=item.href, badge=item.source,
            )
            for item in rows
        ]
        return self._base(parsed, question, summary, ["calendar"],
                          metrics={"Overdue": str(len(buckets["overdue"])),
                                   "This week": str(len(buckets["this_week"]))},
                          cards=_cap(cards),
                          actions=[dto.AssistantActionOutput("Go to Calendar", "/productivity", "module")])

    def _answer_upcoming_meetings(self, parsed, question, asked_by) -> dto.AssistantAnswerOutput:
        snapshot = self._snapshot()
        today = today_iso()
        cards = self._feed_cards(snapshot, ("events", "committee_meetings"),
                                 today, add_days(today, 7), today)
        summary = f"{len(cards)} meeting(s)/event(s) in the next 7 days."
        return self._base(parsed, question, summary, ["events", "committees", "calendar"],
                          metrics={"Next 7 days": str(len(cards))}, cards=cards,
                          actions=[dto.AssistantActionOutput("Go to Calendar", "/productivity", "module"),
                                   dto.AssistantActionOutput("Go to Committees", "/committees", "module")])

    def _answer_pending_reports(self, parsed, question, asked_by) -> dto.AssistantAnswerOutput:
        snapshot = self._snapshot()
        today = today_iso()
        cards = self._feed_cards(snapshot, ("reports_due",), add_days(today, -30), add_days(today, 30), today)
        summary = f"{len(cards)} report-linked action(s) still open (window: ±30 days)."
        return self._base(parsed, question, summary, ["committees", "reports"],
                          metrics={"Open report actions": str(len(cards))}, cards=cards,
                          actions=[dto.AssistantActionOutput("Go to Reports", "/reports", "module")])

    def _budget_metrics(self) -> dict[str, float]:
        dash = reports_dashboard(self._repository)
        return {
            "approved": dash.budget_approved,
            "utilized": dash.budget_utilized,
            "remaining": dash.budget_remaining,
        }

    def _answer_budget_remaining(self, parsed, question, asked_by) -> dto.AssistantAnswerOutput:
        values = self._budget_metrics()
        summary = (
            f"Budget remaining: {_money(values['remaining'])} — of {_money(values['approved'])} "
            f"approved, {_money(values['utilized'])} is utilized (reports module computation)."
        )
        return self._base(parsed, question, summary, ["reports", "finance", "research"],
                          metrics={"Approved": _money(values["approved"]),
                                   "Utilized": _money(values["utilized"]),
                                   "Remaining": _money(values["remaining"])},
                          cards=self._grant_cards(),
                          actions=[dto.AssistantActionOutput("Go to Finance", "/finance", "module"),
                                   dto.AssistantActionOutput("Open Research grants", "/research/grants", "module")])

    # ------------------------------------------------------------- research
    def _publications(self) -> list[UniversalObject]:
        return self._repository.find_by_type(ObjectType.PUBLICATION)

    def _mine_or_all(self, objs: list[UniversalObject], asked_by: str) -> tuple[list[UniversalObject], str]:
        mine = [o for o in objs
                if (getattr(getattr(o, "audit", None), "created_by", "") or "") == asked_by]
        if asked_by != DEFAULT_ASKER and mine:
            return mine, "you created"
        return objs, "in AcademicOS"

    def _pub_card(self, obj: UniversalObject) -> dto.AssistantCardOutput:
        meta = _meta(obj)
        subtitle = " · ".join(part for part in (
            meta.get(KEY_PUBLICATION_TYPE), meta.get(KEY_PUB_YEAR) or (meta.get(KEY_PUB_DATE) or "")[:4],
        ) if part)
        return _card(obj, subtitle=subtitle or None, badge=meta.get(KEY_PUBLICATION_TYPE) or None)

    def _answer_my_publications(self, parsed, question, asked_by) -> dto.AssistantAnswerOutput:
        pubs, scope = self._mine_or_all(self._publications(), asked_by)
        ordered = _sort_by_meta_date(pubs, KEY_PUB_DATE, KEY_PUB_YEAR)
        summary = f"{len(pubs)} publication(s) {scope}."
        return self._base(parsed, question, summary, ["publications"],
                          metrics={"Publications": str(len(pubs))},
                          cards=_cap([self._pub_card(o) for o in ordered]),
                          actions=[dto.AssistantActionOutput("Open Publications", "/publications", "module")])

    def _answer_latest_publication(self, parsed, question, asked_by) -> dto.AssistantAnswerOutput:
        pubs, scope = self._mine_or_all(self._publications(), asked_by)
        ordered = _sort_by_meta_date(pubs, KEY_PUB_DATE, KEY_PUB_YEAR)
        if not ordered:
            summary = f"No publications found {scope}."
        else:
            latest = ordered[0]
            summary = f"Your latest publication is “{latest.title}”." if scope == "you created" \
                else f"The latest publication {scope} is “{latest.title}”."
        return self._base(parsed, question, summary, ["publications"],
                          metrics={"Publications": str(len(pubs))},
                          cards=[self._pub_card(ordered[0])] if ordered else [],
                          actions=[dto.AssistantActionOutput("Open Publications", "/publications", "module")])

    def _answer_publications_this_year(self, parsed, question, asked_by) -> dto.AssistantAnswerOutput:
        year = today_iso()[:4]
        pubs, scope = self._mine_or_all(self._publications(), asked_by)
        this_year = [o for o in pubs
                     if (_meta(o).get(KEY_PUB_YEAR) or (_meta(o).get(KEY_PUB_DATE) or "")[:4]) == year]
        ordered = _sort_by_meta_date(this_year, KEY_PUB_DATE, KEY_PUB_YEAR)
        summary = f"{len(this_year)} publication(s) in {year} ({scope})."
        return self._base(parsed, question, summary, ["publications"],
                          metrics={f"Publications {year}": str(len(this_year))},
                          cards=_cap([self._pub_card(o) for o in ordered]),
                          actions=[dto.AssistantActionOutput("Open Publications", "/publications", "module")])

    def _answer_conference_papers(self, parsed, question, asked_by) -> dto.AssistantAnswerOutput:
        pubs, scope = self._mine_or_all(self._publications(), asked_by)
        conf = [o for o in pubs
                if "conference" in (_meta(o).get(KEY_PUBLICATION_TYPE) or "").lower()
                or (_meta(o).get(KEY_CONFERENCE) or "").strip()]
        ordered = _sort_by_meta_date(conf, KEY_PUB_DATE, KEY_PUB_YEAR)
        summary = f"{len(conf)} conference paper(s) {scope}."
        return self._base(parsed, question, summary, ["publications"],
                          metrics={"Conference papers": str(len(conf))},
                          cards=_cap([self._pub_card(o) for o in ordered]),
                          actions=[dto.AssistantActionOutput("Open Publications", "/publications", "module")])

    def _projects(self) -> list[UniversalObject]:
        return self._repository.find_by_type(ObjectType.RESEARCH_PROJECT)

    def _project_card(self, obj: UniversalObject, by_id: dict[str, UniversalObject] | None = None) -> dto.AssistantCardOutput:
        meta = _meta(obj)
        status = meta.get(KEY_LIFECYCLE_STATUS) or "draft"
        subtitle = status.replace("_", " ")
        if by_id is not None:
            agencies = [by_id[str(rel.target)].title
                        for rel in obj.relationships
                        if rel.kind is RelationshipKind.FUNDED_BY and str(rel.target) in by_id]
            if agencies:
                subtitle = f"{subtitle} · funded by {', '.join(agencies)}"
        return _card(obj, subtitle=subtitle, badge=status)

    def _answer_active_projects(self, parsed, question, asked_by) -> dto.AssistantAnswerOutput:
        projects = self._projects()
        active = [o for o in projects
                  if (_meta(o).get(KEY_LIFECYCLE_STATUS) or "draft") in PROJECT_IN_FLIGHT_STATUSES]
        by_id = {str(o.id): o for o in self._repository.list()}
        summary = f"{len(active)} active research project(s) (statuses: approved/funded/active)."
        return self._base(parsed, question, summary, ["research"],
                          metrics={"Active projects": str(len(active))},
                          cards=_cap([self._project_card(o, by_id) for o in active]),
                          actions=[dto.AssistantActionOutput("Open Research", "/research", "module")])

    def _answer_completed_projects(self, parsed, question, asked_by) -> dto.AssistantAnswerOutput:
        projects = self._projects()
        done = [o for o in projects
                if (_meta(o).get(KEY_LIFECYCLE_STATUS) or "") in ("completed", "closed")]
        summary = f"{len(done)} completed research project(s)."
        return self._base(parsed, question, summary, ["research"],
                          metrics={"Completed projects": str(len(done))},
                          cards=_cap([self._project_card(o) for o in done]),
                          actions=[dto.AssistantActionOutput("Open Research", "/research", "module")])

    def _funder_projects(self, keyword: str) -> list[UniversalObject]:
        agencies = {
            str(o.id): o for o in self._repository.find_by_type(ObjectType.FUNDING_AGENCY)
            if not keyword or token_match(o.title, keyword)
        }
        projects = []
        for obj in self._projects():
            funded_ids = [str(rel.target) for rel in obj.relationships
                          if rel.kind is RelationshipKind.FUNDED_BY]
            if any(target in agencies for target in funded_ids):
                projects.append(obj)
        return projects

    def _answer_projects_by_funder(self, parsed, question, asked_by) -> dto.AssistantAnswerOutput:
        keyword = str(parsed.params.get("keyword") or "").strip()
        projects = self._funder_projects(keyword)
        by_id = {str(o.id): o for o in self._repository.list()}
        label = f" funded by “{keyword}”" if keyword else " with a funding agency linked"
        summary = f"{len(projects)} project(s){label}."
        return self._base(parsed, question, summary, ["research"],
                          metrics={"Projects": str(len(projects))},
                          cards=_cap([self._project_card(o, by_id) for o in projects]),
                          actions=[dto.AssistantActionOutput("Open Research", "/research", "module")])

    def _grants(self) -> list[UniversalObject]:
        return self._repository.find_by_type(ObjectType.GRANT)

    def _grant_cards(self, grants: list[UniversalObject] | None = None) -> list[dto.AssistantCardOutput]:
        by_id = None
        rows = self._grants() if grants is None else grants
        cards: list[dto.AssistantCardOutput] = []
        for obj in rows:
            meta = _meta(obj)
            if by_id is None and any(rel.kind is RelationshipKind.FUNDED_BY for rel in obj.relationships):
                by_id = {str(o.id): o for o in self._repository.list()}
            subtitle = meta.get("grant_number") or ""
            if by_id is not None:
                agencies = [by_id[str(rel.target)].title
                            for rel in obj.relationships
                            if rel.kind is RelationshipKind.FUNDED_BY and str(rel.target) in by_id]
                if agencies:
                    subtitle = f"{subtitle} · {', '.join(agencies)}".strip(" ·")
            stats = {}
            amount = parse_amount(meta.get(KEY_AMOUNT))
            if amount:
                stats["amount"] = _money(amount)
            cards.append(_card(obj, subtitle=subtitle or None, stats=stats))
        return cards

    def _answer_research_grants(self, parsed, question, asked_by) -> dto.AssistantAnswerOutput:
        grants = self._grants()
        total = sum(parse_amount(_meta(o).get(KEY_AMOUNT)) or 0.0 for o in grants)
        summary = f"{len(grants)} research grant(s), sanctioned total ≈ {_money(total)}."
        return self._base(parsed, question, summary, ["research"],
                          metrics={"Grants": str(len(grants)), "Sanctioned": _money(total)},
                          cards=_cap(self._grant_cards(grants)),
                          actions=[dto.AssistantActionOutput("Open Research grants", "/research/grants", "module")])

    def _answer_documents_by_keyword(self, parsed, question, asked_by) -> dto.AssistantAnswerOutput:
        keyword = str(parsed.params.get("keyword") or "").strip()
        documents = self._repository.find_by_type(ObjectType.DOCUMENT)
        by_id = {str(o.id): o for o in self._repository.list()}
        hits: list[UniversalObject] = []
        for obj in documents:
            if not keyword:
                hits.append(obj)
                continue
            meta = _meta(obj)
            haystack = " ".join([obj.title, meta.get("document_type", ""), meta.get("tags", ""),
                                 meta.get("description", "")])
            linked_titles = " ".join(
                by_id[str(rel.target)].title for rel in obj.relationships if str(rel.target) in by_id
            )
            if token_match(haystack, keyword) or token_match(linked_titles, keyword):
                hits.append(obj)
        label = f" matching “{keyword}”" if keyword else ""
        summary = f"{len(hits)} document(s){label} (title, type, tags and linked records searched)."
        cards = []
        for obj in _cap(hits):
            meta = _meta(obj)
            cards.append(_card(obj, subtitle=meta.get("document_type") or None,
                               badge="document"))
        return self._base(parsed, question, summary, ["documents"],
                          metrics={"Documents": str(len(hits))}, cards=cards,
                          actions=[dto.AssistantActionOutput("Open Documents", "/documents", "module")])

    # ------------------------------------------------------------- teaching
    def _answer_attendance_below(self, parsed, question, asked_by) -> dto.AssistantAnswerOutput:
        threshold = float(parsed.params.get("threshold") or 75)
        classes = self._repository.find_by_type(ObjectType.COURSE)
        below_rows: list[tuple[UniversalObject, object]] = []
        for class_obj in classes:
            sessions = attendance_sessions_of_class(self._repository, str(class_obj.id))
            students = enrolled_students(self._repository, str(class_obj.id))
            summary = build_attendance_summary(
                students, sessions, class_id=str(class_obj.id), threshold=threshold
            )
            for row in summary.rows:
                if row.below_threshold:
                    below_rows.append((class_obj, row))
        summary_text = (
            f"{len(below_rows)} enrolment(s) below {threshold:.0f}% attendance "
            f"across {len(classes)} class(es) (teaching module computation; "
            f"no record in a session counts as absent)."
        )
        cards = [
            dto.AssistantCardOutput(
                object_id=row.student_id, object_type="student", title=row.student_name,
                subtitle=f"{class_obj.title} · {row.percentage}% ({row.effective_present}/{row.total})",
                href=f"/students/{row.student_id}", badge="attendance",
                stats={"attendance": f"{row.percentage}%"},
            )
            for class_obj, row in _cap(below_rows)
        ]
        return self._base(parsed, question, summary_text, ["teaching", "students"],
                          metrics={"Below threshold": str(len(below_rows)),
                                   "Threshold": f"{threshold:.0f}%"},
                          cards=cards,
                          actions=[dto.AssistantActionOutput("Go to Teaching", "/teaching", "module")])

    def _answer_pending_grading(self, parsed, question, asked_by) -> dto.AssistantAnswerOutput:
        submissions = [
            o for o in self._repository.find_by_type(ObjectType.SUBMISSION)
            if not (_meta(o).get("graded_at") or "").strip()
        ]
        by_id = {str(o.id): o for o in self._repository.list()}
        per_assignment: dict[str, dict] = {}
        for obj in submissions:
            assignment_id = next(
                (str(rel.target) for rel in obj.relationships
                 if rel.kind is RelationshipKind.BELONGS_TO and str(rel.target) in by_id
                 and by_id[str(rel.target)].object_type is ObjectType.ASSIGNMENT),
                None,
            )
            assignment = by_id.get(assignment_id) if assignment_id else None
            key = assignment_id or str(obj.id)
            slot = per_assignment.setdefault(key, {"assignment": assignment, "count": 0})
            slot["count"] += 1
        summary = (
            f"{len(submissions)} ungraded submission(s) across "
            f"{len(per_assignment)} assignment(s)."
        )
        cards = []
        for slot in _cap(list(per_assignment.values())):
            assignment = slot["assignment"]
            if assignment is None:
                continue
            cards.append(_card(assignment, subtitle="assignment",
                               badge="grading",
                               stats={"ungraded": str(slot["count"])}))
        return self._base(parsed, question, summary, ["teaching"],
                          metrics={"Ungraded submissions": str(len(submissions)),
                                   "Assignments": str(len(per_assignment))},
                          cards=cards,
                          actions=[dto.AssistantActionOutput("Go to Teaching", "/teaching", "module")])

    def _answer_upcoming_classes(self, parsed, question, asked_by) -> dto.AssistantAnswerOutput:
        snapshot = self._snapshot()
        today = today_iso()
        cards = self._feed_cards(snapshot, ("teaching", "attendance_sessions"),
                                 today, add_days(today, 7), today)
        summary = f"{len(cards)} class session(s) scheduled in the next 7 days."
        return self._base(parsed, question, summary, ["teaching", "calendar"],
                          metrics={"Next 7 days": str(len(cards))}, cards=cards,
                          actions=[dto.AssistantActionOutput("Go to Teaching", "/teaching", "module")])

    def _answer_pending_assignments(self, parsed, question, asked_by) -> dto.AssistantAnswerOutput:
        snapshot = self._snapshot()
        today = today_iso()
        cards = self._feed_cards(snapshot, ("assignments",), add_days(today, -7), add_days(today, 14), today)
        summary = f"{len(cards)} assignment deadline(s) in the −7…+14 day window."
        return self._base(parsed, question, summary, ["teaching"],
                          metrics={"Assignments": str(len(cards))}, cards=cards,
                          actions=[dto.AssistantActionOutput("Go to Teaching", "/teaching", "module")])

    # ------------------------------------------------------------- finance
    def _proposals(self) -> list[UniversalObject]:
        return self._repository.find_by_type(ObjectType.PURCHASE)

    def _proposal_card(self, obj: UniversalObject) -> dto.AssistantCardOutput:
        meta = _meta(obj)
        status = meta.get(KEY_PROPOSAL_STATUS) or "draft"
        stats = {}
        cost = parse_amount(meta.get(KEY_ESTIMATED_COST))
        if cost:
            stats["estimated"] = _money(cost)
        return _card(obj, subtitle=f"proposal · {status.replace('_', ' ')}",
                     badge=status, stats=stats)

    def _count_pending_po_rows(self, proposals: list[UniversalObject]) -> int:
        pending = 0
        for obj in proposals:
            for row in _json_list(_meta(obj).get(KEY_PURCHASE_ORDERS)):
                status = str(row.get("status") or "").lower()
                if status not in ("delivered", "closed", "cancelled"):
                    pending += 1
        return pending

    def _answer_budget_summary(self, parsed, question, asked_by) -> dto.AssistantAnswerOutput:
        values = self._budget_metrics()
        utilized_pct = (values["utilized"] / values["approved"] * 100.0) if values["approved"] else 0.0
        summary = (
            f"Budget position: {_money(values['approved'])} approved, "
            f"{_money(values['utilized'])} utilized ({utilized_pct:.0f}%), "
            f"{_money(values['remaining'])} remaining."
        )
        return self._base(parsed, question, summary, ["reports", "finance", "research"],
                          metrics={"Approved": _money(values["approved"]),
                                   "Utilized": _money(values["utilized"]),
                                   "Utilization": f"{utilized_pct:.0f}%",
                                   "Remaining": _money(values["remaining"])},
                          cards=self._grant_cards(),
                          actions=[dto.AssistantActionOutput("Go to Finance", "/finance", "module")])

    def _answer_pending_purchases(self, parsed, question, asked_by) -> dto.AssistantAnswerOutput:
        proposals = self._proposals()
        active = [o for o in proposals
                  if (_meta(o).get(KEY_PROPOSAL_STATUS) or "draft") in ACTIVE_PROPOSAL_STATUSES]
        pending_pos = self._count_pending_po_rows(proposals)
        summary = (
            f"{len(active)} procurement proposal(s) in flight "
            f"({', '.join(ACTIVE_PROPOSAL_STATUSES)}), plus {pending_pos} purchase order(s) "
            f"awaiting delivery/closure."
        )
        return self._base(parsed, question, summary, ["finance"],
                          metrics={"Active proposals": str(len(active)),
                                   "Open POs": str(pending_pos)},
                          cards=_cap([self._proposal_card(o) for o in active]),
                          actions=[dto.AssistantActionOutput("Go to Finance", "/finance", "module")])

    def _answer_recent_procurements(self, parsed, question, asked_by) -> dto.AssistantAnswerOutput:
        proposals = self._proposals()
        done = [o for o in proposals
                if (_meta(o).get(KEY_PROPOSAL_STATUS) or "") in ("completed", "ordered")]
        ordered = _sort_by_meta_date(done, "proposal_date")
        bills = sum(
            1
            for o in proposals
            for row in _json_list(_meta(o).get(KEY_BILLS))
            if str(row.get("payment_status") or "").lower() == "paid"
        )
        summary = (
            f"{len(done)} completed/ordered procurement(s); {bills} bill(s) already paid."
        )
        return self._base(parsed, question, summary, ["finance"],
                          metrics={"Completed procurements": str(len(done)),
                                   "Paid bills": str(bills)},
                          cards=_cap([self._proposal_card(o) for o in ordered]),
                          actions=[dto.AssistantActionOutput("Go to Finance", "/finance", "module")])

    # ------------------------------------------------------------- events
    def _events(self) -> list[UniversalObject]:
        return self._repository.find_by_type(ObjectType.EVENT)

    def _event_card(self, obj: UniversalObject, context: str | None = None) -> dto.AssistantCardOutput:
        meta = _meta(obj)
        subtitle = " · ".join(part for part in (
            meta.get(KEY_EVENT_TYPE), meta.get("start_date"), context,
        ) if part)
        return _card(obj, subtitle=subtitle or None, badge=meta.get(KEY_EVENT_STATUS) or None)

    def _participation_rows(self, obj: UniversalObject) -> list[dict]:
        parsed = parse_json_object(_meta(obj).get(KEY_PARTICIPATION))
        rows = parsed.get("rows") if isinstance(parsed, dict) else None
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
        return _json_list(_meta(obj).get(KEY_PARTICIPATION))

    def _events_with_role(self, roles: tuple[str, ...]) -> list[UniversalObject]:
        out = []
        for obj in self._events():
            for row in self._participation_rows(obj):
                if str(row.get("role") or "").lower() in roles:
                    out.append(obj)
                    break
        return out

    def _answer_upcoming_events(self, parsed, question, asked_by) -> dto.AssistantAnswerOutput:
        event_type = str(parsed.params.get("event_type") or "").strip().lower()
        today = today_iso()
        events = [
            o for o in self._events()
            if (_meta(o).get(KEY_EVENT_STATUS) or "planned") in UPCOMING_EVENT_STATUSES
            and (_meta(o).get("end_date") or _meta(o).get("start_date") or "") >= today
        ]
        if event_type:
            events = [o for o in events
                      if event_type in (_meta(o).get(KEY_EVENT_TYPE) or "").lower()]
        ordered = _sort_by_meta_date(events, "start_date", reverse=False)
        label = f" upcoming {event_type}s" if event_type else " upcoming events"
        summary = f"{len(ordered)}{label} (planned/ongoing, from today)."
        return self._base(parsed, question, summary, ["events"],
                          metrics={f"Upcoming{(' ' + event_type + 's') if event_type else ' events'}":
                                   str(len(ordered))},
                          cards=_cap([self._event_card(o) for o in ordered]),
                          actions=[dto.AssistantActionOutput("Go to Events", "/events", "module")])

    def _answer_events_attended(self, parsed, question, asked_by) -> dto.AssistantAnswerOutput:
        events = _sort_by_meta_date(self._events_with_role(ATTENDEE_ROLES), "end_date", "start_date")
        summary = f"{len(events)} event(s) you attended (participation role: attendee/participant)."
        return self._base(parsed, question, summary, ["events"],
                          metrics={"Attended": str(len(events))},
                          cards=_cap([self._event_card(o, "attended") for o in events]),
                          actions=[dto.AssistantActionOutput("Go to Events", "/events", "module")])

    def _answer_events_organized(self, parsed, question, asked_by) -> dto.AssistantAnswerOutput:
        events = _sort_by_meta_date(self._events_with_role(ORGANIZER_ROLES), "end_date", "start_date")
        summary = f"{len(events)} event(s) on your organising record (organizer/coordinator/convener)."
        return self._base(parsed, question, summary, ["events"],
                          metrics={"Organized": str(len(events))},
                          cards=_cap([self._event_card(o, "organized") for o in events]),
                          actions=[dto.AssistantActionOutput("Go to Events", "/events", "module")])

    def _answer_certificates(self, parsed, question, asked_by) -> dto.AssistantAnswerOutput:
        dash = events_dashboard(self._repository)
        cards: list[dto.AssistantCardOutput] = []
        for obj in self._events():
            meta = _meta(obj)
            issued = parse_json_object(meta.get(KEY_REGISTRATION)).get("certificates_issued") \
                if isinstance(parse_json_object(meta.get(KEY_REGISTRATION)), dict) else 0
            doc_ids = [str(row.get("certificate_document_id"))
                       for row in self._participation_rows(obj) if row.get("certificate_document_id")]
            if (isinstance(issued, int) and issued > 0) or doc_ids:
                card = self._event_card(obj, "certificates")
                if isinstance(issued, int) and issued:
                    card.stats["certificates"] = str(issued)
                if doc_ids:
                    card.stats["document"] = doc_ids[0]
                cards.append(card)
        summary = (
            f"{dash.get('certificates', 0)} certificate(s) on record across "
            f"{len(cards)} event(s) (events module computation)."
        )
        return self._base(parsed, question, summary, ["events"],
                          metrics={"Certificates": str(dash.get("certificates", 0)),
                                   "Events": str(len(cards))},
                          cards=_cap(cards),
                          actions=[dto.AssistantActionOutput("Go to Events", "/events", "module")])

    # ------------------------------------------------------------- committees
    def _answer_committee_meetings(self, parsed, question, asked_by) -> dto.AssistantAnswerOutput:
        snapshot = self._snapshot()
        today = today_iso()
        cards = self._feed_cards(snapshot, ("committee_meetings",),
                                 today, add_days(today, 30), today)
        summary = f"{len(cards)} committee meeting(s) in the next 30 days."
        return self._base(parsed, question, summary, ["committees", "calendar"],
                          metrics={"Next 30 days": str(len(cards))}, cards=cards,
                          actions=[dto.AssistantActionOutput("Go to Committees", "/committees", "module")])

    def _answer_pending_actions(self, parsed, question, asked_by) -> dto.AssistantAnswerOutput:
        from app.application.use_cases.productivity.helpers import committee_action_tasks
        snapshot = self._snapshot()
        actions = [o for o in committee_action_tasks(snapshot.tasks_all) if not task_is_done(o)]
        ordered = _sort_by_meta_date(actions, "due_date", reverse=False)
        summary = f"{len(ordered)} committee action item(s) still open."
        cards = [
            _card(obj, subtitle=("due " + _meta(obj).get("due_date")
                                 if _meta(obj).get("due_date") else None),
                  badge="action", href="/committees")
            for obj in _cap(ordered)
        ]
        return self._base(parsed, question, summary, ["committees"],
                          metrics={"Open actions": str(len(ordered))}, cards=cards,
                          actions=[dto.AssistantActionOutput("Go to Committees", "/committees", "module")])

    def _answer_recent_decisions(self, parsed, question, asked_by) -> dto.AssistantAnswerOutput:
        meetings = self._repository.find_by_type(ObjectType.MEETING)
        by_id = {str(o.id): o for o in self._repository.list()}
        with_decisions = []
        for obj in meetings:
            decisions = _json_list(_meta(obj).get("decisions"))
            if decisions:
                with_decisions.append((obj, [str(d) for d in decisions]))
        ordered = sorted(with_decisions,
                         key=lambda pair: _meta(pair[0]).get("meeting_date") or "",
                         reverse=True)
        summary = f"{len(ordered)} meeting(s) have recorded decisions."
        items: list[dict] = []
        for obj, decisions in _cap(ordered):
            meeting_of = next(
                (by_id[str(rel.target)].title for rel in obj.relationships
                 if rel.kind is RelationshipKind.BELONGS_TO and str(rel.target) in by_id),
                None,
            )
            for decision in _cap(decisions, 3):
                items.append({"title": decision,
                              "subtitle": f"{obj.title} · {_meta(obj).get('meeting_date') or ''}"
                              + (f" · {meeting_of}" if meeting_of else ""),
                              "href": f"/committees/meetings/{obj.id}"})
        return self._base(parsed, question, summary, ["committees"],
                          metrics={"Meetings with decisions": str(len(ordered))},
                          items=_cap(items),
                          actions=[dto.AssistantActionOutput("Go to Committees", "/committees", "module")])

    # ------------------------------------------------------------- reports
    def _answer_report_catalogue(self, parsed, question, asked_by) -> dto.AssistantAnswerOutput:
        kinds = [title for _key, title in REPORT_TITLES.items()]
        summary = (
            f"The Reports module offers {len(kinds)} report kinds: "
            f"{', '.join(list(kinds)[:10])}. Open one to view charts and tables — "
            f"AcademicOS never generates them here, it reuses the Reports module."
        )
        cards = [
            dto.AssistantCardOutput(object_id=key, object_type="report", title=title,
                                    subtitle="report kind", href=f"/reports/{key}", badge="report")
            for key, title in list(REPORT_TITLES.items())[: dto.ANSWER_CARD_LIMIT]
        ]
        return self._base(parsed, question, summary, ["reports"],
                          metrics={"Report kinds": str(len(kinds))}, cards=cards,
                          actions=[dto.AssistantActionOutput("Go to Reports", "/reports", "module")])

    def _answer_module_report_summary(self, parsed, question, asked_by) -> dto.AssistantAnswerOutput:
        module = str(parsed.params.get("module") or "overview")
        data = self._report_metrics(module)
        title = REPORT_TITLES.get(module, f"{module.title()} report")
        if not data:
            summary = (f"The {title} currently exposes no headline numbers "
                       f"(the module may have no records yet).")
        else:
            headline = "; ".join(f"{key}: {value}" for key, value in list(data.items())[:4])
            summary = f"{title} — headline numbers from the existing report endpoint: {headline}."
        return self._base(parsed, question, summary, ["reports", module],
                          metrics={key: str(value) for key, value in data.items()},
                          actions=[dto.AssistantActionOutput(f"Open the {module} report",
                                                             f"/reports/{module}", "module"),
                                   dto.AssistantActionOutput("Go to Reports", "/reports", "module")])

    def _report_metrics(self, kind: str) -> dict[str, object]:
        """Run the *existing* report use case and echo its KPI strip verbatim
        (label → value, exactly what the report page renders as chips) — no
        report logic is duplicated here. Falls back to scalar-flattening for
        outputs without a KPI strip."""
        try:
            output = _run_report_use_case(self._repository, kind)
        except Exception:  # report use cases may legitimately 404 on empty data
            return {}
        raw = asdict(output) if is_dataclass(output) else (output if isinstance(output, dict) else {})
        kpis = raw.get("kpis")
        if isinstance(kpis, list) and kpis:
            metrics: dict[str, object] = {}
            for kpi in kpis[:8]:
                if not isinstance(kpi, dict):
                    continue
                label = str(kpi.get("label") or "").strip()
                value = kpi.get("value")
                if label and value not in (None, ""):
                    metrics[label] = value
            if metrics:
                return metrics
        metrics = {}
        for key, value in raw.items():
            if key in _REPORT_NOISE_KEYS or isinstance(value, bool) or value is None:
                continue
            if isinstance(value, int | float):
                metrics[_humanize(key)] = round(value, 2) if isinstance(value, float) else value
            elif isinstance(value, str) and value and len(metrics) < 8:
                metrics[_humanize(key)] = value[:60]
            if len(metrics) >= 8:
                break
        return metrics

    # ------------------------------------------------------------- search/meta
    def _answer_knowledge_search(self, parsed, question, asked_by) -> dto.AssistantAnswerOutput:
        query = str(parsed.params.get("query") or parsed.query or question).strip()
        skip_types = {ObjectType.SETTINGS, ObjectType.AI_CONVERSATION}
        hits: list[UniversalObject] = []
        for obj in self._repository.list():
            if obj.object_type in skip_types:
                continue
            meta = _meta(obj)
            haystack = obj.title + " " + " ".join(meta.values())
            if token_match(haystack, query):
                hits.append(obj)
        hits.sort(key=lambda o: (0 if token_match(o.title, query) else 1, o.title.lower()))
        summary = (
            f"{len(hits)} knowledge-graph record(s) match “{query}” — reusing the "
            f"universal-object search over titles and metadata (no separate search engine)."
        )
        cards = [_card(obj, subtitle=obj.object_type.value.replace("_", " "))
                 for obj in _cap(hits)]
        return self._base(parsed, question, summary, ["knowledge_graph"],
                          metrics={"Matches": str(len(hits))}, cards=cards,
                          actions=[dto.AssistantActionOutput("Open Objects", "/objects", "module")])

    def _answer_help(self, parsed, question, asked_by) -> dto.AssistantAnswerOutput:
        groups = ", ".join(group for group, _codes in dto.INTENT_GROUPS)
        summary = (
            "I am the AcademicOS Intelligence assistant — local and deterministic. "
            f"Ask me about: {groups}. I answer from your actual AcademicOS data and "
            "link every answer back to the module it came from. Try a suggested "
            "question from the home screen to see the style."
        )
        return self._base(parsed, question, summary, ["assistant"],
                          actions=[dto.AssistantActionOutput("Go to AI Home", "/assistant", "module"),
                                   dto.AssistantActionOutput("Open Reports", "/reports", "module")])

    def _answer_greeting(self, parsed, question, asked_by) -> dto.AssistantAnswerOutput:
        summary = (
            "Hello! I'm AcademicOS Intelligence — ask about today, deadlines, "
            "publications, projects, attendance, purchases, events, committees or reports."
        )
        return self._base(parsed, question, summary, ["assistant"],
                          actions=[dto.AssistantActionOutput("Go to AI Home", "/assistant", "module")])


# ---------------------------------------------------------------------------
# Report bridge — reuse the frozen report use classes by kind
# ---------------------------------------------------------------------------
def _run_report_use_case(repository: ObjectRepository, kind: str):
    """Execute the exact use case the Reports route layer would run (default
    query, no filters). Import-time registry keeps the mapping explicit."""
    if kind == "analytics":
        from app.application.queries.get_analytics_report import GetAnalyticsReportQuery
        from app.application.use_cases.reports.analytics_report import GetAnalyticsReportUseCase
        return GetAnalyticsReportUseCase(repository).execute(GetAnalyticsReportQuery())
    registry = {
        "publications": (
            "app.application.queries.get_publications_report", "GetPublicationsReportQuery",
            "app.application.use_cases.reports.publications_report", "GetPublicationsReportUseCase"),
        "research": (
            "app.application.queries.get_research_report", "GetResearchReportQuery",
            "app.application.use_cases.reports.research_report", "GetResearchReportUseCase"),
        "faculty": (
            "app.application.queries.get_faculty_report", "GetFacultyReportQuery",
            "app.application.use_cases.reports.faculty_report", "GetFacultyReportUseCase"),
        "students": (
            "app.application.queries.get_students_report", "GetStudentsReportQuery",
            "app.application.use_cases.reports.students_report", "GetStudentsReportUseCase"),
        "teaching": (
            "app.application.queries.get_teaching_report", "GetTeachingReportQuery",
            "app.application.use_cases.reports.teaching_report", "GetTeachingReportUseCase"),
        "committees": (
            "app.application.queries.get_committees_report", "GetCommitteesReportQuery",
            "app.application.use_cases.reports.committees_report", "GetCommitteesReportUseCase"),
        "events": (
            "app.application.queries.get_events_report", "GetEventsReportQuery",
            "app.application.use_cases.reports.events_report", "GetEventsReportUseCase"),
        "finance": (
            "app.application.queries.get_finance_report", "GetFinanceReportQuery",
            "app.application.use_cases.reports.finance_report", "GetFinanceReportUseCase"),
    }
    entry = registry.get(kind)
    if entry is None:  # defensive: unknown kinds surface as "no metrics"
        raise KeyError(f"unknown report kind: {kind}")
    import importlib

    query_module, query_name, use_module, use_name = entry
    query_cls = getattr(importlib.import_module(query_module), query_name)
    use_cls = getattr(importlib.import_module(use_module), use_name)
    return use_cls(repository).execute(query_cls())


def _humanize(key: str) -> str:
    return key.replace("_", " ").strip().capitalize()


AssistantCardT = dto.AssistantCardOutput
